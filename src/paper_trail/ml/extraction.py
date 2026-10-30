"""commitment extraction: our llm reads the pages, every answer needs a verbatim receipt

no llm configured = nothing extracted. the old regex rules only ever matched one city's
layout (see the holdout eval), so they're gone
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
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


def excerpt_found(page_text: str, excerpt: str) -> bool:
    """non-empty verbatim substring of the raw page text"""
    return bool(excerpt.strip()) and excerpt in page_text


def source_excerpt(page_text: str, excerpt: str) -> str | None:
    """the excerpt as it really sits on the page (models squash whitespace), or None"""
    if not excerpt.strip():
        return None
    match = re.search(r"\s+".join(map(re.escape, excerpt.split())), page_text)
    return match.group(0) if match else None


PAGE_CHARS = 6000  # per page in the prompt, build_dataset filters labels on it too


def extraction_prompt(profile: LanguageProfile, pages: list[DocumentPage]) -> str:
    """the exact user turn the llm sees, fine-tuning builds its data with this too"""
    body = "\n\n".join(f"--- page {p.page_number} ---\n{p.text[:PAGE_CHARS]}" for p in pages)
    return _PROMPT.format(language=profile.name, pages=body)


# leading section code the prompt asks the model to keep: "M1.2", "Ks1", "Má-1"
_CODE = re.compile(r"^([A-ZÁÉÍÓÖŐÚÜŰ][a-záéíóöőúüű]{0,2}-?\d+(?:\.\d+)*)(?=[\s:.)\-]|$)")


def lead_code(title: str) -> str | None:
    m = _CODE.match(title.strip())
    return m.group(1).rstrip(".") if m else None


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
            return [([p], self._ask([p])) for p in window]
        return [(window, reply)]

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
                if kind in KINDS and receipt:
                    out.append(PolicyCandidate(
                        document_id=0, suggested_type=kind, text=item.text,
                        normalized_title=item.normalized_title, source_page=item.page,
                        code=lead_code(item.normalized_title),
                        source_excerpt=receipt, excerpt_on_page=True))
        return out


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
