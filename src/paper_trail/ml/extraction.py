"""Policy-commitment extraction from a strategy document.

Two implementations behind one interface:

* `RuleBasedExtractor` — deterministic parsing of fixed-layout municipal
  strategy documents (goal headings, numbered measure cards, indicator
  blocks, dated numeric sentences). The labels it recognises — "Stratégiai
  cél", "Measure code", … — come from the active `LanguageProfile`, so a
  differently-worded document family needs a profile, not a code change.
  Works with no network.
* `LLMExtractor` — asks an OpenAI-compatible endpoint for structured output,
  validated with Pydantic and deterministic excerpt verification. Used when
  PAPER_TRAIL_LLM_BASE_URL / PAPER_TRAIL_LLM_MODEL are configured.

Both must produce PolicyCandidate objects that carry page + verbatim excerpt.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from functools import lru_cache

import requests
from pydantic import BaseModel, ValidationError

from ..domain.enums import CandidateType
from ..domain.models import DocumentPage, PolicyCandidate
from .lang import LanguageProfile


def _squash(text: str) -> str:
    return " ".join(text.split())


def excerpt_found(page_text: str, excerpt: str) -> bool:
    """Verbatim check after whitespace normalisation."""
    return _squash(excerpt) in _squash(page_text)


class Extractor(ABC):
    @abstractmethod
    def extract(self, pages: list[DocumentPage]) -> list[PolicyCandidate]:
        ...


# ---------------------------------------------------------------------------
# Rule-based extraction for fixed-layout documents

_NOISE_RE = re.compile(r"http|www\.|%C3|%CC|wp-content|/Documents/", re.IGNORECASE)


@lru_cache(maxsize=8)
def _layout(profile: LanguageProfile):
    """The document-layout patterns, compiled from the profile's labels."""
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
    alt = lambda ls: "|".join(re.escape(l) for l in ls) or r"(?!)"
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
    """Reads the document's own structure — no guessing."""

    def __init__(self, profile: LanguageProfile):
        self._p = _layout(profile)
        self._profile = profile

    def _clean_title(self, title: str, page_text: str) -> str:
        """PDF extraction glues headings onto body sentences — the review
        screen shows the title, so strip the marker and, if the page's own
        goal heading leaked in, strip that too. Source text stays verbatim."""
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

        # the action-plan region: first actual goal heading or measure card
        # to the last measure card — dated-numeric sentences outside it are
        # background statistics (and the TOC mentions the markers as words)
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

        def add(**kw) -> None:
            key = kw["normalized_title"].lower()
            if key in seen_titles:
                return
            seen_titles.add(key)
            out.append(PolicyCandidate(**kw))

        for page in pages:
            text = page.text
            if not text.strip():
                continue

            for m in p["goal"].finditer(text):
                title = self._clean_title(m.group(2), text)
                add(document_id=0, suggested_type=CandidateType.OBJECTIVE,
                    text=_squash(m.group(0)), normalized_title=title,
                    source_page=page.page_number, source_excerpt=_squash(m.group(0)),
                    code=m.group(1))

            for m in p["pillar"].finditer(text):
                title = self._clean_title(m.group(2), text)
                add(document_id=0, suggested_type=CandidateType.OBJECTIVE,
                    text=_squash(m.group(0)), normalized_title=title,
                    source_page=page.page_number, source_excerpt=_squash(m.group(0)),
                    code=m.group(1))

            if p["card"]:
                for m in p["card"].finditer(text):
                    heading = self._heading_before(text, m.start())
                    if not heading:
                        continue
                    # a measure card often spans pages — the metadata block
                    # can sit one or two pages after the code
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
                    continue  # page furniture / grant identifier lines
                if _NOISE_RE.search(sent) or (
                        p["intent"] and not p["intent"].search(sent)):
                    continue  # URL fragments and background statistics
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
        """The measure name sits on the line(s) right before the card
        label (e.g. 'Intézkedés kódja')."""
        prefix = text[max(0, pos - 200): pos]
        lines = [ln.strip() for ln in prefix.split("\n") if ln.strip()]
        if not lines:
            return None
        # last 1–3 short lines form the heading; drop page furniture
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
        # strip glued footnote digits ("korszerűsítése11") but keep real
        # names ending in a digit ("Zöld8", "RÉV8")
        title = p["footnote"].sub(r"\1", title)
        return title or None


# ---------------------------------------------------------------------------
# LLM extraction through any OpenAI-compatible endpoint

class _LLMItem(BaseModel):
    type: str
    normalized_title: str
    text: str
    page: int
    excerpt: str


class _LLMResponse(BaseModel):
    items: list[_LLMItem]


_PROMPT = """You are extracting policy commitments from a municipal
strategy document written in {language}. From the pages below, return ONLY
JSON of the form {{"items": [...]}} where each item is:
  type: one of objective | measure | target | indicator
  normalized_title: short plain name
  text: the full commitment sentence(s)
  page: the printed page number it appears on
  excerpt: a verbatim quote from that page supporting it
Rules: only report what the text actually says; never invent targets, dates
or bodies; if unsure, omit the item. Write titles in {language} as in the
source.

PAGES:
{pages}
"""


class LLMExtractor(Extractor):
    """Structured extraction via any OpenAI-compatible /chat/completions
    endpoint (OpenAI, Ollama, HF TGI/Endpoints, vLLM, Modal)."""

    def __init__(self, base_url: str, api_key: str | None, model: str,
                 profile: LanguageProfile):
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._key = api_key or ""
        self._model = model
        self._profile = profile

    def extract(self, pages: list[DocumentPage]) -> list[PolicyCandidate]:
        candidates: list[PolicyCandidate] = []
        page_text = {p.page_number: p.text for p in pages}
        for i in range(0, len(pages), 4):
            window = pages[i: i + 4]
            body = "\n\n".join(
                f"--- page {p.page_number} ---\n{p.text[:6000]}" for p in window
            )
            resp = requests.post(
                self._url,
                headers={"Authorization": f"Bearer {self._key}"},
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": _PROMPT.format(
                        language=self._profile.name, pages=body)}],
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                },
                timeout=120,
            )
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"]
            try:
                parsed = _LLMResponse.model_validate_json(raw)
            except ValidationError:
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
                excerpt = _squash(item.excerpt)
                on_page = excerpt_found(page_text.get(item.page, ""), excerpt)
                candidates.append(PolicyCandidate(
                    document_id=0, suggested_type=ctype,
                    text=item.text, normalized_title=item.normalized_title,
                    source_page=item.page, source_excerpt=excerpt,
                    excerpt_on_page=on_page,
                ))
        return candidates


def get_extractor(llm_base_url: str | None, llm_api_key: str | None,
                  llm_model: str | None,
                  profile: LanguageProfile) -> Extractor:
    """LLM when configured, otherwise the deterministic document parser."""
    if llm_base_url and llm_model:
        return LLMExtractor(llm_base_url, llm_api_key, llm_model, profile)
    return RuleBasedExtractor(profile)
