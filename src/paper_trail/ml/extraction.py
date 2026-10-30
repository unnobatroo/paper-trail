"""commitment extraction: our llm reads the pages, every answer needs a verbatim receipt

no llm configured = nothing extracted. the old regex rules only ever matched one city's
layout (see the holdout eval), so they're gone
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from itertools import chain

import openai
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..domain.enums import CandidateType
from ..domain.models import DocumentPage, PolicyCandidate
from .client import model_client
from .lang import LanguageProfile

log = logging.getLogger(__name__)

KINDS = {CandidateType.OBJECTIVE, CandidateType.MEASURE, CandidateType.TARGET,
         CandidateType.INDICATOR}

_PROMPT = """You are extracting policy commitments from a municipal
strategy document written in {language}. From the pages below, return ONLY
JSON of the form {{"items": [...]}} where each item is:
  type: one of objective | measure | target | indicator
  normalized_title: short plain name of the commitment. if the document prints a code
    in front of it, keep that code exactly as printed, never invent or reuse one
  text: the commitment in one or two sentences
  page: the N from the "--- page N ---" marker above the text you quote
  excerpt: one short verbatim quote from that page supporting it
Numbered or coded headings are objectives
or measures too. Rules: only report what the text actually says; never invent
targets, dates or bodies; if unsure, omit the item. Write titles in {language}
as in the source.

Example (made up, not from these pages). Page text: "3.4 Green roofs on schools.
Install green roofs on four primary schools by 2027."
Item: {{"type": "measure", "normalized_title": "3.4 Green roofs on schools",
"text": "Green roofs go on four primary schools by 2027.", "page": 1,
"excerpt": "Install green roofs on four primary schools by 2027."}}

PAGES:
{pages}
"""


def excerpt_found(page_text: str, excerpt: str) -> bool:
    """non-empty verbatim substring of the raw page text"""
    return bool(excerpt.strip()) and excerpt in page_text


def source_excerpt(page_text: str, excerpt: str) -> str | None:
    """the excerpt as it really sits on the page, or None. whitespace doesn't count: pdf text
    has spaces mid-word ("bizonyít ékalapú", "létr e") and models quote the clean word"""
    want = "".join(excerpt.split())
    if not want:
        return None
    # page chars minus whitespace, plus where each one sits in the real text
    at = [i for i, ch in enumerate(page_text) if not ch.isspace()]
    start = "".join(page_text[i] for i in at).find(want)
    if start < 0:
        return None
    return page_text[at[start]:at[start + len(want) - 1] + 1]


PAGE_CHARS = 6000  # per page in the prompt, build_dataset filters labels on it too


def extraction_prompt(profile: LanguageProfile, pages: list[DocumentPage]) -> str:
    """the exact user turn the llm sees, fine-tuning builds its data with this too"""
    body = "\n\n".join(f"--- page {p.page_number} ---\n{p.text[:PAGE_CHARS]}" for p in pages)
    return _PROMPT.format(language=profile.name, pages=body)


# leading section code the prompt asks the model to keep: "M1.2", "Ks1", "Má-1"
# or a dotted number ("1.01"); one dot minimum so a bare year isn't a code
_CODE = re.compile(r"^([A-ZÁÉÍÓÖŐÚÜŰ][a-záéíóöőúüű]{0,2}-?\d+(?:\.\d+)*|\d+(?:\.\d+)+)"
                   r"(?=[\s:.)\-]|$)")


def lead_code(title: str) -> str | None:
    m = _CODE.match(title.strip())
    return m.group(1).rstrip(".") if m else None


def grounded_title(title: str, text: str, page_text: str) -> tuple[str, str | None]:
    """title + its code, minus a code the page never prints. the model likes to invent
    "M1.01" for "1.01", or reuse codes from training docs, same rule as receipts"""
    code = lead_code(title)
    if code is None or "".join(code.split()) in "".join(page_text.split()):
        return title, code
    rest = title.strip()[len(code):].lstrip(" :.-–")
    return (rest or text[:120]), None


class _Item(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # caps go out as json-schema maxLength, otherwise small models paste whole paragraphs,
    # run out of tokens and the json never closes
    type: str
    normalized_title: str = Field(max_length=120)
    text: str = Field(max_length=400)
    page: int
    excerpt: str = Field(max_length=300)


class _Reply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[_Item]


def form_row(quote: str, labels: tuple[str, ...]) -> bool:
    """fact-sheet row ("Időtáv 2021-2030", "Felelős: Jegyző", "célkitűzés kódja Ms-1.3"):
    starts with a label, or is labels + codes + numbers with barely any words left"""
    low = " ".join(quote.casefold().split()).lstrip("•-–* :")
    hits = [label for label in labels if label in low]
    if not hits:
        return False
    if any(low.startswith(label) for label in hits):
        return True
    for label in sorted(hits, key=len, reverse=True):
        low = low.replace(label, " ")
    return len(re.findall(r"[^\W\d_]{3,}", low)) < 4


def same_passage(a: str, b: str) -> bool:
    """two quotes of the same text: a long shared run, not a stray "a város" or two.
    numbers decide: "200 fa" and "500 fa" are two commitments however alike the rest is"""
    a, b = sorted((re.sub(r"\W+", " ", x.casefold()).strip() for x in (a, b)), key=len)
    if not a or not b or not set(re.findall(r"\d+", a)) <= set(re.findall(r"\d+", b)):
        return False
    run = SequenceMatcher(None, a, b, autojunk=False).find_longest_match().size
    return run >= 20 and run >= 0.5 * len(a)


def dedupe(cands: list[PolicyCandidate]) -> list[PolicyCandidate]:
    # same page, same quoted passage = same commitment twice (window + half retries,
    # heading + body). first one wins, like langextract's multi-pass merge
    out: list[PolicyCandidate] = []
    for c in cands:
        if not any(k.source_page == c.source_page
                   and same_passage(k.source_excerpt, c.source_excerpt) for k in out):
            out.append(c)
    return out


class LLMExtractor:
    """any openai-style /chat/completions endpoint, json-schema constrained"""

    def __init__(self, client, model: str, profile: LanguageProfile, window: int = 4,
                 concurrency: int = 1, max_tokens: int = 2048):
        self._client = client
        self._model = model
        self._profile = profile
        self._window = max(1, window)
        # parallel windows so the server batches them on the gpu
        self._concurrency = max(1, concurrency)
        # set it ourselves, a server default can chop the json mid-object
        self._max_tokens = max_tokens

    def _ask(self, pages: list[DocumentPage]) -> _Reply | None:
        """one call. None when the reply isn't valid json for the schema, http errors raise"""
        resp = self._client.chat.completions.create(
            model=self._model, temperature=0, max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": extraction_prompt(self._profile, pages)}],
            response_format={"type": "json_schema", "json_schema": {
                "name": "policy_candidates", "strict": True,
                "schema": _Reply.model_json_schema()}},
            # hybrid qwen3 thinks the whole budget away and answers nothing otherwise
            extra_body=({"chat_template_kwargs": {"enable_thinking": False}}
                        if "qwen3" in self._model.lower() else None))
        try:
            return _Reply.model_validate_json(resp.choices[0].message.content or "")
        except ValidationError:
            return None

    def _ask_window(self, window: list[DocumentPage]) -> list[tuple[list[DocumentPage],
                                                                    _Reply | None]]:
        """a window, or page by page when it fails, one bad answer can't lose four pages"""
        try:
            reply = self._ask(window)
        except openai.APIError as exc:
            if len(window) == 1:
                raise
            log.warning("llm window failed (%s), retrying per page", exc)
            reply = None
        if reply is None and len(window) > 1:
            return [([p], self._ask_page(p)) for p in window]
        if reply is None:
            return [(window, self._ask_page(window[0], failed=True))]
        return [(window, reply)]

    def _ask_page(self, page: DocumentPage, depth: int = 2,
                  failed: bool = False) -> _Reply | None:
        """one page; bad json is nearly always a dense page blowing max_tokens mid-object,
        so ask about each half instead. receipts still get checked against the whole page"""
        reply = None if failed else self._ask([page])
        lines = page.text.splitlines()
        if reply is not None or depth == 0 or len(lines) < 2:
            return reply
        mid = len(lines) // 2
        halves = [self._ask_page(page.model_copy(update={"text": "\n".join(part)}), depth - 1)
                  for part in (lines[:mid], lines[mid:])]
        items = [i for h in halves if h for i in h.items]
        return _Reply(items=items) if any(halves) else None

    def extract(self, pages: list[DocumentPage]) -> list[PolicyCandidate]:
        windows = [pages[i:i + self._window] for i in range(0, len(pages), self._window)]
        with ThreadPoolExecutor(self._concurrency) as pool:
            # map keeps page order and re-raises the first http error
            answers = list(chain.from_iterable(pool.map(self._ask_window, windows)))
        text = {p.page_number: p.text for p in pages}
        out = []
        for scope, reply in answers:
            if reply is None:
                log.warning("invalid llm json for pages %s, skipped",
                            [p.page_number for p in scope])
                continue
            for item in reply.items:
                kind = CandidateType(item.type) if item.type in CandidateType else None
                receipt = source_excerpt(text.get(item.page, ""), item.excerpt)
                if kind in KINDS and receipt and not form_row(receipt,
                                                              self._profile.form_labels):
                    title, code = grounded_title(item.normalized_title, item.text,
                                                 text[item.page])
                    out.append(PolicyCandidate(
                        document_id=0, suggested_type=kind, text=item.text,
                        normalized_title=title, source_page=item.page, code=code,
                        source_excerpt=receipt, excerpt_on_page=True))
        return dedupe(out)


class NoExtractor:
    """no llm configured: ingest still records the document, it just finds nothing"""

    def extract(self, pages: list[DocumentPage]) -> list[PolicyCandidate]:
        log.warning("no llm configured (LLM_*), nothing extracted")
        return []


def get_extractor(base_url: str | None, api_key: str | None, model: str | None,
                  profile: LanguageProfile, window: int = 4,
                  concurrency: int = 1) -> LLMExtractor | NoExtractor:
    if base_url and model:
        return LLMExtractor(model_client(base_url, api_key), model, profile, window, concurrency)
    return NoExtractor()
