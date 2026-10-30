"""evidence search: commitment -> official sources -> ranked links for a person

fixed pipeline, no agents: route -> search + registry -> fetch once -> chunk ->
embed once -> hybrid top-k -> rerank -> read the passage -> suggest
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from decimal import Decimal
from urllib.parse import urlsplit

from ..domain.enums import EvidenceFlag, EvidencePolarity, Status
from ..domain.models import (
    BudgetRecord,
    Commitment,
    EvidenceItem,
    EvidenceLink,
    OfficialSource,
)
from ..ml import entities, matching
from ..ml.accountability import PassageAuditor
from ..ml.embeddings import EmbeddingProvider
from ..ml.lang import LanguageProfile
from ..ml.ner import NoNer
from ..ml.nlp import Analysis, HuSpacyAnalyzer
from ..ml.rerank import Reranker
from ..repositories.postgres.index import PostgresPageStore, PostgresVectorIndex
from ..repositories.store import EvidenceRepository
from ..sources import fetch as fetching
from ..sources.chunking import structure_chunks
from ..sources.fetch import FetchedPage
from ..sources.web_search import SearchProvider, allowed
from .gazetteer import PlaceResolver

TOP_K = 5
_CHUNK = 2400  # bigger chunks won the evals
_CHUNK_STRIDE = _CHUNK - 400  # overlap so edge evidence doesn't get cut
# panic bound for corrupt input only, truncates + warns, real docs go in full
_DEFAULT_MAX_DOC_CHARS = 4_000_000

@dataclass
class _Run:
    """one find_evidence call: where progress goes, where warnings land. passed down
    explicitly, the service is shared by parallel jobs"""
    say: Callable[[str], None] = lambda _msg: None
    warnings: list[str] = field(default_factory=list)


def _key(commitment: Commitment) -> str:
    """full sentences find nothing on site: search, ~10 words + the code"""
    return " ".join(commitment.title.split()[:10] + [commitment.code or ""]).strip()


class EvidenceService:
    def __init__(
            self,
            repo: EvidenceRepository,
            search: SearchProvider,
            embedder: EmbeddingProvider,
            fetcher=None,
            reranker: Reranker | None = None,
            candidates: int = 20,
            max_doc_chars: int = _DEFAULT_MAX_DOC_CHARS,
            page_store: PostgresPageStore | None = None,
            vector_index: PostgresVectorIndex | None = None,
            baseline_year: int | None = None,
            profile: LanguageProfile | None = None,
            allowed_domains: tuple[str, ...] = (),
            analyzer: HuSpacyAnalyzer | None = None,
            crawler=None,
            max_fetch_workers: int = 2,
            parser=None,
            ner=None,
    ):
        self._analyzer = analyzer
        self._crawler = crawler
        self._fetch_workers = max(1, max_fetch_workers)  # scripts skip the settings bound
        self._repo = repo
        self._search = search
        self._embed = embedder
        self._fetch = fetcher or (lambda url, domains: fetching.fetch(url, domains, parser=parser))
        self._reranker = reranker
        self._candidates = candidates
        self._max_doc_chars = max_doc_chars
        self._baseline_year = baseline_year
        # locale cues all live in lang.py
        self._profile = profile or LanguageProfile.empty()
        self._auditor = PassageAuditor(self._profile)
        self._places = PlaceResolver(repo, self._auditor)
        # bootstrap passes gliner, bare years otherwise
        self._ner = ner or NoNer()
        self._extra_domains = {d.lower() for d in allowed_domains}
        # page text + chunk vectors live next to the evidence, same database
        self._pages = page_store or PostgresPageStore(repo.dsn)
        self._index = vector_index or PostgresVectorIndex(
            repo.dsn, ts_config=self._profile.ts_config)

    def find_evidence(
            self,
            commitment: Commitment,
            progress=None,
            warnings: list[str] | None = None,
    ) -> list[EvidenceLink]:
        """run the search for one commitment. progress(msg) fires per stage so a cold run
        doesn't look frozen, warnings collect what the reviewer should know"""
        run = _Run(progress or (lambda _msg: None), [] if warnings is None else warnings)
        return self._discover(commitment, run)

    def _discover(self, commitment: Commitment, run: _Run) -> list[EvidenceLink]:
        run.say("Finding official sources…")
        registry, domains, routed, owner_term = self._sources(commitment)
        if not domains:
            run.warnings.append("No evidence sources configured — the "
                       "official_sources registry is empty and "
                       "ALLOWED_DOMAINS is unset.")
        if self._crawler is not None:
            try:
                for source in self._crawler.discover(domains):
                    self._repo.upsert_official_source(source)
                registry, domains, routed, owner_term = self._sources(commitment)
            except Exception as exc:
                run.warnings.append(f"Source discovery failed ({type(exc).__name__})")
        urls = self._collect_urls(commitment, registry, domains, routed, owner_term)
        run.say(f"Found {len(urls)} official pages to check — reading them…")
        # fetching is pure io, go parallel so one slow server doesn't stall everything
        with ThreadPoolExecutor(max_workers=self._fetch_workers) as pool:
            pages = [
                p for p in pool.map(
                    lambda u: self._fetch_page(u, registry, domains),
                    urls) if p
            ]
        run.say(f"Read {len(pages)} pages — indexing their text…")
        if not pages:
            return []

        self._places.refresh()
        links: list[EvidenceLink] = []
        for page, snippet, sim in self._rank(commitment, pages, run)[:TOP_K]:
            # a reviewer already decided on this source, hands off
            if self._repo.reviewed_evidence_id(commitment.id, page.url) is not None:
                continue
            links.append(self._record(commitment, page, snippet, sim, registry))
        return links

    def _record(self, commitment: Commitment, page: FetchedPage, snippet: str, sim: float,
                registry: list[OfficialSource]) -> EvidenceLink:
        """one matched passage -> evidence row, money, artifacts, suggested link

        all of it reads the matched excerpt, a 100-page report has every cue somewhere
        """
        ev = self._evidence(commitment, page, snippet, registry)
        mentions = self._relevant_money(snippet)
        stale = self._predates_strategy(page)
        ev.status_hint, ev.status_excerpt = self._status(page, snippet, ev, mentions, stale)
        ev.id = self._repo.add_evidence(ev)
        artifacts = [self._repo.link_artifact(pid, ev.id, ev.polarity)
                     for pid in ev.procurement_ids]
        for mention in mentions:
            self._repo.add_budget(BudgetRecord(
                evidence_id=ev.id,
                kind=mention.kind,
                amount_huf=mention.amount_huf,
                currency=mention.currency, amount_native=mention.amount_native,
                amount_raw=mention.amount_raw,
                fiscal_year=mention.year,
                description=mention.sentence,
                source_url=page.url,
            ))
        features = matching.compute_features(commitment, ev, sim, self._profile, self._ner)
        has_budget = bool(self._repo.budgets_for_evidence(ev.id))
        rel, reasons = matching.suggest_relationship(features, has_budget)
        rel, reasons = self._audited_hint(ev, artifacts, rel, reasons)
        if stale:
            reasons.append(
                f"published {page.published_on.year} — predates the "
                "strategy, so it can only be context")
        link = EvidenceLink(
            commitment_id=commitment.id,
            evidence_id=ev.id,
            features=features,
            score=matching.score(features),
            suggested_relationship=rel,
            reasons=reasons,
        )
        link.id = self._repo.add_link(link)
        return link

    def _evidence(self, commitment: Commitment, page: FetchedPage, snippet: str,
                  registry: list[OfficialSource]) -> EvidenceItem:
        """entities, places and audit cues, passage only"""
        analysis = self._analyzer.analyze(snippet) if self._analyzer else Analysis()
        found = self._ner.find(snippet)
        streets = found.places
        audit = self._auditor.audit(snippet)
        return EvidenceItem(
            commitment_id=commitment.id,
            url=page.url,
            title=page.title,
            publisher=self._publisher(page.url, registry),
            published_on=page.published_on,
            snippet=snippet,
            organisations=list(dict.fromkeys(found.orgs + analysis.organisations)),
            locations=list(dict.fromkeys(
                streets + analysis.locations + self._places.resolve(snippet, page.url, streets))),
            dates_mentioned=list(dict.fromkeys(found.dates + analysis.dates)),
            polarity=audit.polarity,
            flags=audit.flags,
            procurement_ids=audit.procurement_ids,
            parcels=audit.parcels,
        )

    def _status(self, page: FetchedPage, snippet: str, ev: EvidenceItem, mentions: list,
                stale: bool) -> tuple[Status, str | None]:
        if stale:
            return Status.BACKGROUND, None
        if ev.polarity == EvidencePolarity.TERMINATION:
            # "works started ... then the contract got cancelled" isn't progress
            return Status.UNKNOWN, None
        is_report = entities.is_report_doc(page.url, page.title, self._profile)
        return entities.classify_status(snippet, self._profile, is_report=is_report,
                                        has_money=bool(mentions))

    def _audited_hint(self, ev: EvidenceItem, artifacts: list, rel, reasons: list[str]):
        """amendments, cancellations and maintenance-only talk cap the auto hint"""
        flags = self._auditor.effective_flags(ev, artifacts)
        if ev.polarity != EvidencePolarity.AFFIRMATIVE:
            reasons.append(f"the passage reports a {ev.polarity.value}, not progress")
            if EvidenceFlag.REGRESSION_WARNING not in flags:
                flags.append(EvidenceFlag.REGRESSION_WARNING)
        return self._auditor.cap(rel, reasons, flags)

    def _sources(self, commitment: Commitment):
        """registry rows for this commitment: the municipality's own + the asset owner's,
        a district-only search makes fake gaps for a water main.
        gives (rows, allowed domains, owner-only domains, owner name)
        """
        owner = commitment.asset_owner_jurisdiction
        rows = [s for s in self._repo.official_sources() if s.jurisdiction in (None, owner)]
        general = self._allowed([s for s in rows if s.jurisdiction is None])
        routed = self._allowed([s for s in rows if s.jurisdiction == owner]) - general
        term = next((s.publisher for s in rows if s.jurisdiction == owner and s.publisher), "")
        return rows, general | routed, routed, term

    def _allowed(self, registry: list[OfficialSource]) -> set[str]:
        """ssrf allowlist = configured domains + every registry host"""
        # hostname, not netloc: "x.hu:8443" would never match a fetched url's host
        return self._extra_domains | {h for d in registry if (h := urlsplit(d.url).hostname)}

    def _collect_urls(self, commitment: Commitment,
                      registry: list[OfficialSource],
                      domains: set[str], routed: set[str] = frozenset(),
                      owner_term: str = "") -> list[str]:
        urls: list[str] = []
        query = _key(commitment)
        for domain in sorted(domains):
            # owner's name narrows a big utility/city site down to the right asset
            q = f"{query} {owner_term}".strip() if domain in routed else query
            try:
                hits = self._search.search(f"site:{domain} {q}", max_results=TOP_K)
            except Exception:
                hits = []
            urls.extend(h.url for h in hits)
        urls.extend(d.url for d in registry)
        # dedupe, keep order, allowlist only
        return [u for u in dict.fromkeys(u.split("#")[0] for u in urls) if allowed(u, domains)]

    def _fetch_page(self, url: str, registry: list[OfficialSource],
                    domains: set[str]) -> FetchedPage | None:
        """fetch once, the page store caches text/title/date"""
        cached = self._pages.get(url)
        if cached is not None:
            return cached
        page = self._fetch(url, domains)
        if page is None:
            return None
        page = FetchedPage(url, self._better_title(url, page.title, registry),
                           page.text, page.published_on)
        self._pages.put(page)
        return page

    @staticmethod
    def _better_title(url: str, fetched: str,
                      registry: list[OfficialSource]) -> str:
        """registry docs have real titles, downloads are often just a filename"""
        if fetched == url or _FILENAME_RE.search(fetched):
            for d in registry:
                if d.url.split("?")[0] == url.split("?")[0]:
                    return d.title
        return fetched

    def _predates_strategy(self, page: FetchedPage) -> bool:
        """older than the strategy: fine as context, its 'done' talk isn't progress"""
        return (self._baseline_year is not None
                and page.published_on is not None
                and page.published_on.year < self._baseline_year)

    @staticmethod
    def _publisher(url: str, registry: list[OfficialSource]) -> str:
        """publisher from the registry, unknown hosts get their hostname, never a guess"""
        host = urlsplit(url).hostname or ""
        for d in registry:
            shost = urlsplit(d.url).hostname or ""
            if shost and (host == shost or host.endswith("." + shost)
                          or shost.endswith("." + host)):
                return d.publisher or host
        return host

    def _relevant_money(self, snippet: str) -> list:
        """money from the matched excerpt: explicit currency, sane amount, deduped"""
        found = {}
        for m in entities.extract_money(snippet, self._profile):
            if m.kind is None or m.amount_native is None:
                continue
            if (m.currency == self._profile.currency
                    and Decimal(m.amount_native) < self._profile.min_amount):
                continue
            found.setdefault((m.currency, m.amount_native, m.kind), m)
        return list(found.values())

    def _index_page(self, page: FetchedPage, run: _Run) -> None:
        """chunk + embed once per (page, model), re-runs never re-embed. truncation warns"""
        if len(page.text) > self._max_doc_chars:
            run.warnings.append(f"{page.title or page.url} is larger than the safety limit "
                       f"({self._max_doc_chars:,} chars), only the first part was searched.")
        model = self._embed.model_name
        if self._index.has(page, model, _CHUNK):
            return
        chunks = structure_chunks(page.text[:self._max_doc_chars], _CHUNK,
                                  _CHUNK - _CHUNK_STRIDE, run.warnings.append)
        if chunks:
            self._pages.put(page)  # vectors hang off the stored page
            vectors = self._embed.embed(chunks)
            self._index.put(page, model, _CHUNK, list(zip(chunks, vectors, strict=True)))

    def _rank(self, commitment: Commitment, pages: list[FetchedPage],
              run: _Run) -> list[tuple[FetchedPage, str, float]]:
        """all chunks -> hybrid top-k -> rerank -> best per doc"""
        query_text = " ".join(
            [commitment.title, commitment.summary, commitment.code or ""]
        )
        q = self._embed.embed([query_text])[0]

        for i, page in enumerate(pages):
            run.say(f"Indexing page {i + 1}/{len(pages)} — {page.title[:60]}")
            self._index_page(page, run)
        top = self._index.match(
            q, query_text, self._embed.model_name, _CHUNK, pages,
            self._candidates)

        run.say("Ranking the best candidates…")
        if self._reranker is None:
            run.warnings.append("Ranked by text similarity only — no reranker is loaded.")
        elif top:
            # reranker can 429 or time out, retrieval order beats losing the job
            try:
                ce = self._reranker.score(query_text, [c[1] for c in top])
            except Exception as exc:
                run.warnings.append(f"Reranker failed ({type(exc).__name__}), "
                                    "ranked by text similarity only.")
            else:
                top = [c for _, c in sorted(zip(ce, top, strict=True), key=lambda r: r[0],
                                            reverse=True)]

        # best chunk per doc, drop near-dupes so broad reports don't crowd out
        # the specific ones
        seen, out = set(), []
        seen_texts: set[str] = set()
        kept_titles: list[set[str]] = []
        stop = self._profile.title_stopwords
        for row in top:
            page = row[0]
            if page.url in seen:
                continue
            text_key = hashlib.sha256(page.text.encode()).hexdigest()[:16]
            if text_key in seen_texts:
                continue
            title_tokens = _title_tokens(page.title, stop)
            if any(_titles_same_doc(title_tokens, t)
                   for t in kept_titles):
                continue
            seen.add(page.url)
            seen_texts.add(text_key)
            kept_titles.append(title_tokens)
            out.append(row)
        return out


# a "title" that's just a filename
_FILENAME_RE = re.compile(
    r"\.(pdf|docx?|xlsx?|pptx?|odt|ods|rtf|csv|txt|zip)$", re.I)


def _title_tokens(title: str, stopwords) -> set[str]:
    return {t for t in re.sub(r"[\W_]+", " ", title.lower()).split()
            if t not in stopwords and len(t) > 1}


def _titles_same_doc(a: set[str], b: set[str]) -> bool:
    """same title + period = same doc at two urls, different years = keep both"""
    if not a or not b:
        return False
    ya, yb = {t for t in a if t.isdigit()}, {t for t in b if t.isdigit()}
    if ya != yb:
        return False
    return len(a & b) / len(a | b) >= 0.8
