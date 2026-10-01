"""Evidence discovery: commitment → official sources → ranked, reviewable links.

Fixed pipeline, no agent behaviour: site-restricted queries plus the
official document registry → fetch each hit once → chunk the FULL
document (never silently truncated) → embed once and cache by content
hash → retrieve the top chunks → cross-encoder rerank → deterministic
entity/money extraction → heuristic relationship suggestion → human
review.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from pathlib import Path
from urllib.parse import urlsplit

from ..domain.enums import Status
from ..domain.models import (
    BudgetRecord,
    Commitment,
    EvidenceItem,
    EvidenceLink,
    OfficialSource,
)
from ..ml import entities, matching
from ..ml.embeddings import EmbeddingProvider
from ..ml.lang import LanguageProfile
from ..ml.rerank import Reranker
from ..repositories.cache import (
    FilePageStore,
    FileVectorIndex,
    PageStore,
    VectorIndex,
)
from ..repositories.store import EvidenceRepository
from ..sources import fetch as fetching
from ..sources.fetch import FetchedPage
from ..sources.web_search import SearchProvider, allowed

TOP_K = 5
_CHUNK = 2400  # evaluated: larger semantic units retrieve better
_CHUNK_STRIDE = _CHUNK - 400  # overlap so evidence at chunk edges isn't split
# Emergency bound against corrupt/pathological input only — hitting it
# truncates AND warns; normal official documents are processed in full.
_DEFAULT_MAX_DOC_CHARS = 4_000_000

# per-run state — two evidence jobs running on the shared service must not
# overwrite each other's progress callback or warnings list
_run_warnings: ContextVar[list[str] | None] = ContextVar(
    "pt_warnings", default=None)
_run_progress: ContextVar[Callable[[str], None] | None] = ContextVar(
    "pt_progress", default=None)


def _key(commitment: Commitment) -> str:
    """The web-search query. Full sentences (e.g. unedited target titles)
    return nothing on site:-restricted search — keep the first ~10 words
    plus the document code."""
    words = commitment.title.split()[:10]
    parts = [" ".join(words)]
    if commitment.code:
        parts.append(commitment.code)
    return " ".join(parts)


class EvidenceService:
    def __init__(
        self,
        repo: EvidenceRepository,
        search: SearchProvider,
        embedder: EmbeddingProvider,
        cache_dir: Path | str | None = None,
        fetcher=None,
        reranker: Reranker | None = None,
        candidates: int = 20,
        max_doc_chars: int = _DEFAULT_MAX_DOC_CHARS,
        page_store: PageStore | None = None,
        vector_index: VectorIndex | None = None,
        baseline_year: int | None = None,
        profile: LanguageProfile | None = None,
        allowed_domains: tuple[str, ...] = (),
    ):
        self._repo = repo
        self._search = search
        self._embed = embedder
        self._fetch = fetcher or fetching.fetch
        self._reranker = reranker
        self._candidates = candidates
        self._max_doc_chars = max_doc_chars
        self._baseline_year = baseline_year
        # language profile: every locale-specific cue list lives in lang.py
        from ..ml.lang import get_profile
        self._profile = profile or get_profile("")
        self._extra_domains = {d.lower() for d in allowed_domains}
        # caches: explicit stores win (Supabase/pgvector); otherwise the
        # original on-disk layout under cache_dir
        if page_store is None or vector_index is None:
            if cache_dir is None:
                raise ValueError(
                    "EvidenceService needs cache_dir or explicit stores")
            page_store = page_store or FilePageStore(Path(cache_dir))
            vector_index = vector_index or FileVectorIndex(Path(cache_dir))
        self._pages = page_store
        self._index = vector_index
        self.warnings: list[str] = []
        self._progress = lambda msg: None

    # -- public ------------------------------------------------------------

    def _say(self, msg: str) -> None:
        progress = _run_progress.get()
        (progress if progress is not None else self._progress)(msg)

    def _warn(self, msg: str) -> None:
        warnings = _run_warnings.get()
        (warnings if warnings is not None else self.warnings).append(msg)

    def find_evidence(
        self,
        commitment: Commitment,
        progress=None,
        warnings: list[str] | None = None,
    ) -> list[EvidenceLink]:
        """Run the bounded discovery pipeline for one commitment.

        `progress(msg)` is called at each stage so the UI can show that a
        cold first run is working, not hung. `warnings` collects truncation
        notices for this run — pass a list when running jobs concurrently;
        otherwise they land on `self.warnings` as before.
        """
        if warnings is None:
            self.warnings = warnings = []
        w_tok = _run_warnings.set(warnings)
        p_tok = _run_progress.set(progress or (lambda msg: None))
        try:
            return self._discover(commitment)
        finally:
            _run_warnings.reset(w_tok)
            _run_progress.reset(p_tok)

    def _discover(self, commitment: Commitment) -> list[EvidenceLink]:
        self._say("Finding official sources…")
        registry = self._repo.official_sources()
        domains = self._allowed(registry)
        if not domains:
            self._warn("No evidence sources configured — the "
                       "official_sources registry is empty and "
                       "PAPER_TRAIL_ALLOWED_DOMAINS is unset.")
        urls = self._collect_urls(commitment, registry, domains)
        self._say(f"Found {len(urls)} official pages to check — reading them…")
        # fetches are pure I/O waits — run them concurrently so a few slow
        # official servers don't stall the whole search
        with ThreadPoolExecutor(max_workers=6) as pool:
            pages = [
                p for p in pool.map(
                    lambda u: self._fetch_page(u, registry, domains),
                    urls) if p
            ]
        self._say(f"Read {len(pages)} pages — indexing their text…")
        if not pages:
            return []

        links: list[EvidenceLink] = []
        for page, snippet, sim in self._rank(commitment, pages)[:TOP_K]:
            ev = EvidenceItem(
                commitment_id=commitment.id,
                url=page.url,
                title=page.title,
                publisher=self._publisher(page.url, registry),
                published_on=page.published_on,
                snippet=snippet,
                organisations=entities.extract_organisations(
                    page.text, self._profile),
                locations=entities.extract_locations(
                    page.text, self._profile),
                dates_mentioned=entities.extract_dates(
                    page.text, self._profile),
            )
            # status and money are judged on the matched excerpt, not the
            # whole document — a 100-page report always contains every cue
            # and dozens of unrelated figures somewhere
            mentions = self._relevant_money(snippet)
            is_report = entities.is_report_doc(page.url, page.title, self._profile)
            stale = self._predates_strategy(page)
            hint, excerpt = entities.classify_status(
                snippet, self._profile,
                is_report=is_report, has_money=bool(mentions))
            if stale:
                hint, excerpt = Status.BACKGROUND, None
            ev.status_hint, ev.status_excerpt = hint, excerpt
            ev.id = self._repo.add_evidence(ev)

            for mention in mentions:
                self._repo.add_budget(BudgetRecord(
                    evidence_id=ev.id,
                    kind=mention.kind,
                    amount_huf=mention.amount_huf,
                    amount_raw=mention.amount_raw,
                    fiscal_year=mention.year,
                    description=mention.sentence,
                    source_url=page.url,
                ))

            features = matching.compute_features(commitment, ev, sim,
                                             self._profile)
            has_budget = bool(self._repo.budgets_for_evidence(ev.id))
            rel, reasons = matching.suggest_relationship(features, has_budget)
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
            links.append(link)
        return links

    # -- internals ----------------------------------------------------------

    def _allowed(self, registry: list[OfficialSource]) -> set[str]:
        """The SSRF allowlist = configured domains ∪ every host in the
        official-source registry. The registry is DB data, so the allowlist
        follows the data, not the code."""
        return self._extra_domains | {
            urlsplit(d.url).netloc.lower() for d in registry
            if urlsplit(d.url).netloc
        }

    def _collect_urls(self, commitment: Commitment,
                      registry: list[OfficialSource],
                      domains: set[str]) -> list[str]:
        urls: list[str] = []
        query = _key(commitment)
        for domain in sorted(domains):
            try:
                hits = self._search.search(f"site:{domain} {query}", max_results=TOP_K)
            except Exception:
                hits = []
            urls.extend(h.url for h in hits)
        urls.extend(d.url for d in registry)
        # de-dupe, keep order, allowlist only
        seen, out = set(), []
        for u in urls:
            u = u.split("#")[0]
            if u not in seen and allowed(u, domains):
                seen.add(u)
                out.append(u)
        return out

    def _fetch_page(self, url: str, registry: list[OfficialSource],
                    domains: set[str]) -> FetchedPage | None:
        """Fetch once; the page store caches text + title + date."""
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
        """Registry docs have human titles; file downloads often only
        yield a filename."""
        if fetched == url or _FILENAME_RE.search(fetched):
            for d in registry:
                if d.url.split("?")[0] == url.split("?")[0]:
                    return d.title
        return fetched

    def _predates_strategy(self, page: FetchedPage) -> bool:
        """Published before the tracked strategy existed — it can provide
        context, but its 'completed/under way' cues can't be progress."""
        return (self._baseline_year is not None
                and page.published_on is not None
                and page.published_on.year < self._baseline_year)

    @staticmethod
    def _publisher(url: str, registry: list[OfficialSource]) -> str:
        """Publisher is registry data (the official_sources rows); a host
        with no registry entry gets its own hostname — never a guess."""
        host = urlsplit(url).netloc.lower()
        for d in registry:
            shost = urlsplit(d.url).netloc.lower()
            if shost and (host == shost or host.endswith("." + shost)
                          or shost.endswith("." + host)):
                return d.publisher or host
        return host

    # -- money ---------------------------------------------------------------

    _MIN_AMOUNT_HUF = 10_000  # municipal context — smaller scraps are noise

    def _relevant_money(self, snippet: str) -> list:
        """Money figures from the matched excerpt only — explicit currency,
        plausible amount, deduplicated by (value, kind)."""
        out, seen = [], set()
        for m in entities.extract_money(snippet, self._profile):
            if m.kind is None or m.amount_huf is None:
                continue
            if m.amount_huf < self._MIN_AMOUNT_HUF:
                continue
            key = (m.amount_huf, m.kind)
            if key in seen:
                continue
            seen.add(key)
            out.append(m)
        return out

    # -- retrieval -----------------------------------------------------------

    def _doc_chunks(self, page: FetchedPage) -> list[str]:
        """Chunk the full document; only the emergency bound may cut it —
        and it always leaves a visible warning."""
        text = page.text
        if len(text) > self._max_doc_chars:
            text = text[: self._max_doc_chars]
        return [text[i: i + _CHUNK]
                for i in range(0, len(text), _CHUNK_STRIDE)]

    def _warn_if_oversized(self, page: FetchedPage) -> None:
        """The emergency bound truncates — the user must always see it."""
        if len(page.text) > self._max_doc_chars:
            self._warn(
                f"{page.title or page.url} is larger than the safety "
                f"limit ({self._max_doc_chars:,} chars) — only the first "
                "part was searched.")

    def _embed_and_store(self, page: FetchedPage) -> list[tuple[str, list[float]]]:
        chunks = self._doc_chunks(page)
        vectors = self._embed.embed(chunks)
        pairs = list(zip(chunks, vectors))
        self._index.put(page, self._embed.model_name, _CHUNK, pairs)
        return pairs

    def _ensure_indexed(self, page: FetchedPage) -> None:
        """Populate the vector index for a page without pulling cached
        vectors back — the remote index only needs a 1-row `has()` check."""
        self._warn_if_oversized(page)
        if not self._index.has(page, self._embed.model_name, _CHUNK):
            self._embed_and_store(page)

    def _doc_vectors(self, page: FetchedPage) -> list[tuple[str, list[float]]]:
        """Chunks + embeddings for a document, cached in the vector index
        so re-running 'Find evidence' never re-embeds unchanged text."""
        self._warn_if_oversized(page)
        cached = self._index.get(page, self._embed.model_name, _CHUNK)
        if cached is not None:
            return cached
        return self._embed_and_store(page)

    def _rank(self, commitment: Commitment, pages: list[FetchedPage],
              ) -> list[tuple[FetchedPage, str, float]]:
        """All chunks → hybrid (dense+lexical) top-k → cross-encoder
        rerank → best per doc."""
        query_text = " ".join(
            [commitment.title, commitment.summary, commitment.code or ""]
        )
        q = self._embed.embed([query_text])[0]

        for i, page in enumerate(pages):
            self._say(
                f"Indexing page {i + 1}/{len(pages)} — {page.title[:60]}")
            self._ensure_indexed(page)
        top = self._index.match(
            q, query_text, self._embed.model_name, _CHUNK, pages,
            self._candidates)

        self._say("Ranking the best candidates…")
        if self._reranker is None:
            self._warn(
                "Ranked by text similarity only — no reranker is loaded.")
        elif top:
            ce = self._reranker.score(query_text, [c[1] for c in top])
            top = [c for _, c in sorted(zip(ce, top),
                                        key=lambda r: -r[0])]

        # one evidence candidate per source document: its best chunk —
        # and drop effectively redundant pages so broad reports don't
        # crowd out more specific results
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


# a "title" that is just a document filename — any office/archive type
_FILENAME_RE = re.compile(
    r"\.(pdf|docx?|xlsx?|pptx?|odt|ods|rtf|csv|txt|zip)$", re.I)


def _title_tokens(title: str, stopwords) -> set[str]:
    return {t for t in re.sub(r"[\W_]+", " ", title.lower()).split()
            if t not in stopwords and len(t) > 1}


def _titles_same_doc(a: set[str], b: set[str]) -> bool:
    """Near-identical titles describing the same period = same document at
    two URLs (e.g. a report PDF linked from two pages). Years differing
    means a *different* edition — keep both."""
    if not a or not b:
        return False
    ya, yb = {t for t in a if t.isdigit()}, {t for t in b if t.isdigit()}
    if ya != yb:
        return False
    inter = len(a & b)
    return inter / max(len(a | b), 1) >= 0.8
