"""Policy-commitment extraction from the strategy PDF.

Two implementations behind one interface:

* `RuleBasedExtractor` — deterministic parsing of the Józsefváros Climate
  Strategy's fixed layout (goal headers, numbered "Intézkedés kódja" measure
  cards, indicator blocks, dated numeric sentences). Works with no network.
* `LLMExtractor` — asks an OpenAI-compatible endpoint for structured output,
  validated with Pydantic and deterministic excerpt verification. Used when
  PAPER_TRAIL_LLM_BASE_URL / PAPER_TRAIL_LLM_MODEL are configured.

Both must produce PolicyCandidate objects that carry page + verbatim excerpt.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod

import requests
from pydantic import BaseModel, ValidationError

from ..domain.enums import CandidateType
from ..domain.models import DocumentPage, PolicyCandidate


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
# Rule-based extraction for this document's layout

_CODE = r"([AMS][a-z]?\d+(?:\.\d+)*)"
_GOAL_RE = re.compile(rf"{_CODE}\s+Stratégiai cél[:：]?\s*(.+)")
_PILLAR_RE = re.compile(rf"{_CODE}\s+Tematikus cél[:：]?\s*(.+)")
_CARD_RE = re.compile(rf"Intézkedés kódja\s*\n?\s*{_CODE}\.")
_META_RES = re.compile(r"Felelős\s+(.+)")
_META_TIME = re.compile(r"Időtáv\s+(.+)")
_TARGET_RE = re.compile(r"([^.]*\b20\d{2}[^.]*(?:%|m2|m²|fő|db|m-en| Ft)[^.]*\.)")

# A dated-numeric sentence only counts as a target inside the action-plan
# region (goals + measure cards), and only when it states intent — the
# situation-analysis chapters are full of statistics with the same shape.
_INTENT_RE = re.compile(
    r"cél|irányoz|irányít|tervez|növel|csökkent|elér|megvalós|felszámol|"
    r"kialakít|fejleszt|javít|bevezet|biztosít|fenntart|ültet|korszerűsít|"
    r"támogat",
    re.IGNORECASE,
)
_NOISE_RE = re.compile(r"http|www\.|%C3|%CC|wp-content|/Documents/", re.IGNORECASE)

_UNIT_RE = re.compile(r"(m2|m²|%|db|fő/év|fő|mm|°C|kWh|Ft)")
_VALUE_RE = re.compile(r"(\d[\d\s]*(?:[.,]\d+)?)\s*(%|m2|m²|db|fő|mm|°C|kWh|Ft)")


class RuleBasedExtractor(Extractor):
    """Reads the strategy's own structure — no guessing."""

    def extract(self, pages: list[DocumentPage]) -> list[PolicyCandidate]:
        out: list[PolicyCandidate] = []
        seen_titles: set[str] = set()

        # the action-plan region: first actual goal heading or measure card
        # to the last measure card — dated-numeric sentences outside it are
        # background statistics (and the TOC mentions the markers as words)
        def is_plan_page(p: DocumentPage) -> bool:
            return bool(
                _GOAL_RE.search(p.text) or _PILLAR_RE.search(p.text)
                or _CARD_RE.search(p.text)
            )

        plan_pages = [p.page_number for p in pages if is_plan_page(p)]
        plan_start = min(plan_pages) if plan_pages else len(pages)
        card_pages = [p.page_number for p in pages
                      if _CARD_RE.search(p.text)]
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

            for m in _GOAL_RE.finditer(text):
                title = _squash(m.group(2)).rstrip(".")
                add(document_id=0, suggested_type=CandidateType.OBJECTIVE,
                    text=_squash(m.group(0)), normalized_title=title,
                    source_page=page.page_number, source_excerpt=_squash(m.group(0)),
                    code=m.group(1))

            for m in _PILLAR_RE.finditer(text):
                title = _squash(m.group(2)).rstrip(".")
                add(document_id=0, suggested_type=CandidateType.OBJECTIVE,
                    text=_squash(m.group(0)), normalized_title=title,
                    source_page=page.page_number, source_excerpt=_squash(m.group(0)),
                    code=m.group(1))

            for m in _CARD_RE.finditer(text):
                heading = self._heading_before(text, m.start())
                if not heading:
                    continue
                # a measure card often spans pages — the metadata block can
                # sit one or two pages after the code
                tail = text[m.end():]
                for np in pages[page.page_number: page.page_number + 2]:
                    tail += "\n" + np.text

                org = _META_RES.search(tail)
                time = _META_TIME.search(tail)
                add(document_id=0, suggested_type=CandidateType.MEASURE,
                    text=heading, normalized_title=heading,
                    source_page=page.page_number,
                    source_excerpt=_squash(text[max(0, m.start() - 160): m.end()]),
                    code=m.group(1),
                    responsible_org=_squash(org.group(1)) if org else None,
                    timeframe=_squash(time.group(1))[:160] if time else None)
            if not (plan_start <= page.page_number <= plan_end):
                continue
            for m in _TARGET_RE.finditer(text):
                sent = _squash(m.group(0))
                if len(sent) < 40 or len(sent) > 400:
                    continue
                if "KEHOP" in sent or "Klímastratégiája" in sent:
                    continue  # page furniture / grant identifier lines
                if _NOISE_RE.search(sent) or not _INTENT_RE.search(sent):
                    continue  # URL fragments and background statistics
                year = re.search(r"20\d{2}", sent)
                value = _VALUE_RE.search(sent)
                add(document_id=0, suggested_type=CandidateType.TARGET,
                    text=sent, normalized_title=sent[:120],
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

    @staticmethod
    def _heading_before(text: str, pos: int) -> str | None:
        """The measure name sits on the line(s) right before 'Intézkedés kódja'."""
        prefix = text[max(0, pos - 200): pos]
        lines = [ln.strip() for ln in prefix.split("\n") if ln.strip()]
        if not lines:
            return None
        # last 1–3 short lines form the heading; drop page furniture
        head: list[str] = []
        for ln in reversed(lines):
            if re.match(r"^\d+$", ln) or ln.startswith("KEHOP-"):
                break
            if len(ln) > 160:
                break
            head.insert(0, ln)
            if len(head) == 3 or re.match(r"^[A-ZÁÉÍÓÖŐÚÜŰ\"„]", ln):
                break
        title = _squash(" ".join(head))
        title = re.sub(r"^.*?Intézkedés kódja\s*", "", title)
        # strip glued footnote digits ("korszerűsítése11") but keep real
        # names ending in a digit ("Zöld8", "RÉV8")
        title = re.sub(r"([a-záéíóöőúüű])\d{2,}$", r"\1", title)
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


_PROMPT = """You are extracting policy commitments from a Hungarian municipal
climate strategy (Józsefváros). From the pages below, return ONLY JSON of the
form {"items": [...]} where each item is:
  type: one of objective | measure | target | indicator
  normalized_title: short plain name
  text: the full commitment sentence(s)
  page: the printed page number it appears on
  excerpt: a verbatim quote from that page supporting it
Rules: only report what the text actually says; never invent targets, dates or
bodies; if unsure, omit the item. Write titles in Hungarian as in the source.

PAGES:
{pages}
"""


class LLMExtractor(Extractor):
    """Structured extraction via any OpenAI-compatible /chat/completions
    endpoint (OpenAI, Ollama, HF TGI/Endpoints, vLLM, Modal)."""

    def __init__(self, base_url: str, api_key: str | None, model: str):
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._key = api_key or ""
        self._model = model

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
                    "messages": [{"role": "user", "content": _PROMPT.format(pages=body)}],
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
                  llm_model: str | None) -> Extractor:
    """LLM when configured, otherwise the deterministic document parser."""
    if llm_base_url and llm_model:
        return LLMExtractor(llm_base_url, llm_api_key, llm_model)
    return RuleBasedExtractor()
