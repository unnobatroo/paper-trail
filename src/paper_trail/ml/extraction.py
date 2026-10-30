"""commitment extraction from a strategy doc

RuleBasedExtractor reads fixed layouts, LLMExtractor talks to any openai-style chat
endpoint, HybridExtractor runs both. every candidate needs a verbatim receipt or it's out
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from functools import lru_cache

import openai
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..domain.enums import CandidateType
from ..domain.models import DocumentPage, PolicyCandidate
from .client import model_client
from .lang import LanguageProfile

log = logging.getLogger(__name__)


def _squash(text: str) -> str:
    return " ".join(text.split())


def excerpt_found(page_text: str, excerpt: str) -> bool:
    """non-empty verbatim substring of the raw page text"""
    return bool(excerpt.strip()) and excerpt in page_text


def source_excerpt(page_text: str, excerpt: str) -> str | None:
    if not excerpt.strip():
        return None
    match = re.search(r"\s+".join(re.escape(w) for w in excerpt.split()), page_text)
    return match.group(0) if match else None


class Extractor(ABC):
    @abstractmethod
    def extract(self, pages: list[DocumentPage]) -> list[PolicyCandidate]:
        ...


# rules for fixed-layout docs

_NOISE_RE = re.compile(r"http|www\.|%C3|%CC|wp-content|/Documents/", re.IGNORECASE)


@lru_cache(maxsize=8)
def _layout(profile: LanguageProfile):
    """layout patterns, compiled from the profile's labels"""
    code = rf"({profile.code_pattern})"
    labels = "|".join(
        re.escape(lb) for lb in
        (*profile.goal_labels, *profile.pillar_labels, profile.card_label,
         profile.indicator_label) if lb)
    struct_re = (
        rf"^\s*\d*[\s.]*(?:{labels})[:：]?\s*"
        rf"|^\s*{re.escape(profile.card_label)}\s+\S+\.?\s*"
        if labels else r"(?!)")
    struct = re.compile(struct_re, re.IGNORECASE)

    def alt(ls):
        return "|".join(re.escape(l) for l in ls) or r"(?!)"

    return {
        "code": code,
        "goal": re.compile(rf"{code}\s+(?:{alt(profile.goal_labels)})"
                           rf"[:：]?\s*(.+)"),
        "pillar": re.compile(rf"{code}\s+(?:{alt(profile.pillar_labels)})"
                             rf"[:：]?\s*(.+)"),
        "card": re.compile(rf"{re.escape(profile.card_label)}\s*\n?\s*"
                           rf"{code}\.") if profile.card_label else None,
        "meta_res": re.compile(
            rf"{re.escape(profile.responsible_label)}\s+(.+)")
        if profile.responsible_label else None,
        "meta_time": re.compile(
            rf"{re.escape(profile.timeframe_label)}\s+(.+)")
        if profile.timeframe_label else None,
        "target": re.compile(
            rf"([^.]*\b20\d{{2}}[^.]*\s*(?:{profile.units_re})[^.]*\.)")
        if profile.units_re else None,
        "intent": re.compile(profile.intent_re, re.IGNORECASE)
        if profile.intent_re else None,
        "value": re.compile(
            rf"(\d[\d\s]*(?:[.,]\d+)?)\s*({profile.units_re})")
        if profile.units_re else None,
        "struct": struct,
        "upper": re.compile(rf"^[{profile.upper_chars}\"„]"),
        "footnote": re.compile(rf"([{profile.lower_chars}])\d{{2,}}$"),
    }


class RuleBasedExtractor(Extractor):
    """reads the doc's own structure, no guessing"""

    def __init__(self, profile: LanguageProfile):
        self._p = _layout(profile)
        self._profile = profile

    def _clean_title(self, title: str, page_text: str) -> str:
        """pdf text glues headings onto sentences. strip the marker (and a leaked goal heading)
        for the title, the source text stays verbatim
        """
        t = _squash(title)
        t = self._p["struct"].sub("", t)
        for m in list(self._p["goal"].finditer(page_text)) \
                 + list(self._p["pillar"].finditer(page_text)):
            head = _squash(m.group(2)).rstrip(".")
            if head and t.startswith(head):
                t = t[len(head):]
        t = re.sub(r"\s+([,.;:])", r"\1", t).strip(" .,;:-")
        return t or title

    def extract(self, pages: list[DocumentPage]) -> list[PolicyCandidate]:
        p = self._p
        out: list[PolicyCandidate] = []
        seen_titles: set[str] = set()

        # action plan = first goal heading/card to the last card, numbers outside it
        # are background stats (or the toc)
        def is_plan_page(pg: DocumentPage) -> bool:
            return bool(
                p["goal"].search(pg.text) or p["pillar"].search(pg.text)
                or (p["card"] and p["card"].search(pg.text))
            )

        plan_pages = [pg.page_number for pg in pages if is_plan_page(pg)]
        plan_start = min(plan_pages) if plan_pages else len(pages)
        card_pages = [pg.page_number for pg in pages
                      if p["card"] and p["card"].search(pg.text)]
        plan_end = max(card_pages) if card_pages else len(pages)

        raw_pages = {page.page_number: page.text for page in pages}

        def add(**kw) -> None:
            receipt = source_excerpt(raw_pages[kw["source_page"]], kw["source_excerpt"])
            if receipt is None:
                return
            kw["source_excerpt"] = receipt
            kw["excerpt_on_page"] = True
            key = kw["normalized_title"].lower()
            if key in seen_titles:
                return
            seen_titles.add(key)
            out.append(PolicyCandidate(**kw))

        for page in pages:
            text = page.text
            if not text.strip():
                continue

            # strategic + thematic goal headings, same shape
            for m in [*p["goal"].finditer(text), *p["pillar"].finditer(text)]:
                add(document_id=0, suggested_type=CandidateType.OBJECTIVE,
                    text=_squash(m.group(0)), normalized_title=self._clean_title(m.group(2), text),
                    source_page=page.page_number, source_excerpt=_squash(m.group(0)),
                    code=m.group(1))

            if p["card"]:
                for m in p["card"].finditer(text):
                    heading = self._heading_before(text, m.start())
                    if not heading:
                        continue
                    # cards span pages, metadata can trail the code by 1-2 pages
                    tail = text[m.end():]
                    for np_ in pages[page.page_number: page.page_number + 2]:
                        tail += "\n" + np_.text

                    org = p["meta_res"].search(tail) if p["meta_res"] else None
                    time = p["meta_time"].search(tail) if p["meta_time"] else None
                    add(document_id=0, suggested_type=CandidateType.MEASURE,
                        text=heading,
                        normalized_title=self._clean_title(heading, text),
                        source_page=page.page_number,
                        source_excerpt=_squash(
                            text[max(0, m.start() - 160): m.end()]),
                        code=m.group(1),
                        responsible_org=_squash(org.group(1)) if org else None,
                        timeframe=_squash(time.group(1))[:160] if time else None)
            if not (plan_start <= page.page_number <= plan_end):
                continue
            if not p["target"]:
                continue
            for m in p["target"].finditer(text):
                sent = _squash(m.group(0))
                if len(sent) < 40 or len(sent) > 400:
                    continue
                if any(nw in sent for nw in self._profile.noise_words):
                    continue  # page furniture / grant ids
                if _NOISE_RE.search(sent) or (
                        p["intent"] and not p["intent"].search(sent)):
                    continue  # url fragments, background stats
                year = re.search(r"20\d{2}", sent)
                value = p["value"].search(sent) if p["value"] else None
                add(document_id=0, suggested_type=CandidateType.TARGET,
                    text=sent,
                    normalized_title=self._clean_title(sent, text)[:120],
                    source_page=page.page_number, source_excerpt=sent,
                    deadline_year=int(year.group()) if year else None,
                    target_value=(
                        float(value.group(1)
                              .replace(" ", "").replace("\u00a0", "")
                              .replace(",", "."))
                        if value else None
                    ),
                    unit=value.group(2) if value else None)

        return out

    def _heading_before(self, text: str, pos: int) -> str | None:
        """measure name sits on the line(s) right above the card label ('Intézkedés kódja')"""
        prefix = text[max(0, pos - 200): pos]
        lines = [ln.strip() for ln in prefix.split("\n") if ln.strip()]
        if not lines:
            return None
        # last 1-3 short lines are the heading, drop the furniture
        p = self._p
        head: list[str] = []
        for ln in reversed(lines):
            if re.match(r"^\d+$", ln) or any(
                    ln.startswith(nw)
                    for nw in self._profile.noise_words):
                break
            if len(ln) > 160:
                break
            head.insert(0, ln)
            if len(head) == 3 or p["upper"].match(ln):
                break
        title = _squash(" ".join(head))
        if self._profile.card_label:
            title = re.sub(
                rf"^.*?{re.escape(self._profile.card_label)}\s*", "", title)
        # strip glued footnote digits ("korszerűsítése11"), keep names like "Zöld8"
        title = p["footnote"].sub(r"\1", title)
        return title or None


# llm extraction, any openai-style endpoint

class _LLMItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # caps go out as json-schema maxLength, otherwise small models copy whole paragraphs,
    # run out of tokens and the json never closes
    type: str
    normalized_title: str = Field(max_length=120)
    text: str = Field(max_length=400)
    page: int
    excerpt: str = Field(max_length=300)


class _LLMResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[_LLMItem]


_PROMPT = """You are extracting policy commitments from a municipal
strategy document written in {language}. From the pages below, return ONLY
JSON of the form {{"items": [...]}} where each item is:
  type: one of objective | measure | target | indicator
  normalized_title: short plain name, keep a leading code such as "M1.2"
  text: the commitment in one or two sentences
  page: the N from the "--- page N ---" marker above the text you quote
  excerpt: one short verbatim quote from that page supporting it
Coded headings such as "M1.2 Zöld középületek" or "Sz1.3.1 ..." are objectives
or measures too. Rules: only report what the text actually says; never invent
targets, dates or bodies; if unsure, omit the item. Write titles in {language}
as in the source.

PAGES:
{pages}
"""


class LLMExtractor(Extractor):
    """structured extraction via any openai-style /chat/completions endpoint"""

    def __init__(self, client, model: str, profile: LanguageProfile, window: int = 4,
                 concurrency: int = 1, max_tokens: int = 2048):
        self._client = client  # openai sdk client, see client.py
        self._model = model
        self._profile = profile
        self._window = max(1, window)
        # parallel windows so the server batches them on the gpu
        self._concurrency = max(1, concurrency)
        # set it ourselves, a server default can chop the json mid-object
        self._max_tokens = max_tokens

    def _ask(self, pages: list[DocumentPage]) -> _LLMResponse | None:
        """one chat call. None if the reply isn't valid json for the schema, http errors raise"""
        body = "\n\n".join(
            f"--- page {p.page_number} ---\n{p.text[:6000]}" for p in pages)
        request = {
            "model": self._model,
            "messages": [{"role": "user", "content": _PROMPT.format(
                language=self._profile.name, pages=body)}],
            "temperature": 0,
            "max_tokens": self._max_tokens,
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "policy_candidates", "strict": True,
                "schema": _LLMResponse.model_json_schema()}},
        }
        if "qwen3" in self._model.lower():
            # hybrid qwen3 burns the whole budget thinking and returns empty content otherwise
            request["chat_template_kwargs"] = {"enable_thinking": False}
        extra = request.pop("chat_template_kwargs", None)
        resp = self._client.chat.completions.create(
            **request, extra_body={"chat_template_kwargs": extra} if extra else None)
        raw = resp.choices[0].message.content or ""
        try:
            return _LLMResponse.model_validate_json(raw)
        except ValidationError:
            return None

    def _ask_window(self, window: list[DocumentPage]) -> list:
        # bad window reply -> retry per page, one dumb answer can't lose four pages
        try:
            responses = [(window, self._ask(window))]
        except openai.APIError as exc:
            # timeout/5xx on a big window -> one call per page
            if len(window) == 1:
                raise
            log.warning("LLM window failed (%s), retrying per page", exc)
            responses = [(window, None)]
        if responses[0][1] is None and len(window) > 1:
            responses = [([p], self._ask([p])) for p in window]
        return responses

    def extract(self, pages: list[DocumentPage]) -> list[PolicyCandidate]:
        from concurrent.futures import ThreadPoolExecutor

        candidates: list[PolicyCandidate] = []
        page_text = {p.page_number: p.text for p in pages}
        windows = [pages[i: i + self._window] for i in range(0, len(pages), self._window)]
        with ThreadPoolExecutor(self._concurrency) as pool:
            # map keeps page order and re-raises the first http error
            answered = list(pool.map(self._ask_window, windows))
        for responses in answered:
            for scope, parsed in responses:
                if parsed is None:
                    log.warning(
                        "invalid LLM JSON for pages %s — skipped",
                        [p.page_number for p in scope])
                    continue
                for item in parsed.items:
                    try:
                        ctype = CandidateType(item.type)
                    except ValueError:
                        ctype = CandidateType.UNCLEAR
                    if ctype not in (
                            CandidateType.OBJECTIVE, CandidateType.MEASURE,
                            CandidateType.TARGET, CandidateType.INDICATOR,
                    ):
                        continue
                    excerpt = source_excerpt(page_text.get(item.page, ""), item.excerpt) or ""
                    on_page = excerpt_found(
                        page_text.get(item.page, ""), excerpt)
                    if not on_page:
                        continue
                    candidates.append(PolicyCandidate(
                        document_id=0, suggested_type=ctype,
                        text=item.text, normalized_title=item.normalized_title,
                        source_page=item.page, source_excerpt=excerpt,
                        excerpt_on_page=on_page,
                    ))
        return candidates


class HybridExtractor(Extractor):
    """rules first, the llm adds what they can't see

    rules nail every coded heading, the llm finds prose commitments and docs without codes.
    llm items repeating a rule hit on the same page get dropped
    """

    def __init__(self, rules: Extractor, llm: Extractor):
        self._rules, self._llm = rules, llm

    def extract(self, pages: list[DocumentPage]) -> list[PolicyCandidate]:
        from difflib import SequenceMatcher

        found = self._rules.extract(pages)

        def norm(text: str) -> str:
            return re.sub(r"\W+", " ", text.casefold()).strip()

        def same(a: PolicyCandidate, b: PolicyCandidate) -> bool:
            if a.source_page != b.source_page:
                return False
            x, y = norm(a.normalized_title or a.text), norm(b.normalized_title or b.text)
            return x in norm(b.text) or y in norm(a.text) or SequenceMatcher(
                None, x, y).ratio() >= 0.6
        for cand in self._llm.extract(pages):
            if not any(same(cand, known) for known in found):
                found.append(cand)
        return found


def get_extractor(llm_base_url: str | None, llm_api_key: str | None,
                  llm_model: str | None,
                  profile: LanguageProfile, window: int = 4,
                  concurrency: int = 1) -> Extractor:
    """rules + llm when one's configured, else just rules"""
    if llm_base_url and llm_model:
        return HybridExtractor(RuleBasedExtractor(profile), LLMExtractor(
            model_client(llm_base_url, llm_api_key), llm_model, profile, window, concurrency))
    return RuleBasedExtractor(profile)
