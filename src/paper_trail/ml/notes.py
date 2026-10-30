"""plain-english notes on queue items, written by our own llm

one chat call per item: what the source-language text says, in words a non-expert gets,
plus a suggested decision. a note is a hint for the reviewer, never a decision
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

import openai
from pydantic import BaseModel, ConfigDict, Field

from ..domain.models import Note
from .client import ask_json
from .lang import LanguageProfile

log = logging.getLogger(__name__)

_PROMPT = """You help a reviewer who reads no {language} and knows nothing about climate
policy. They check whether items pulled from a municipal climate strategy, and evidence
found for them, are real.

Glossary of terms in these documents:
{glossary}

{task}

Answer ONLY with JSON:
  title_en: short plain-english name, keep a leading code such as "M1.2"
  summary_en: one or two plain sentences saying what it means in practice, no jargon
  suggestion: accept | reject | unsure
  reason_en: one sentence why

Item:
{item}"""

_CANDIDATE_TASK = """Decide if this item is a real commitment of the district (a goal, a
measure, a target or an indicator it promises). Reject headings, background facts,
descriptions of the past and fragments. Use unsure when it can't be told from the text."""

_LINK_TASK = """Decide if the evidence passage shows work on the commitment (planning,
money, contracts, building, finishing). Reject passages that only share words with it or
talk about something else. Use unsure when the passage is too vague."""


class _Reply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # caps keep a small model from pasting whole paragraphs and losing the closing brace
    title_en: str = Field(max_length=140)
    summary_en: str = Field(max_length=500)
    suggestion: str = Field(pattern="^(accept|reject|unsure)$")
    reason_en: str = Field(max_length=300)


class NoteWriter:
    def __init__(self, client, model: str, profile: LanguageProfile, concurrency: int = 1):
        self._client = client  # openai sdk client, see client.py
        self._model = model
        self._profile = profile
        self._concurrency = max(1, concurrency)

    def _ask(self, task: str, item: str) -> _Reply | None:
        glossary = "\n".join(f"- {t}: {m}" for t, m in self._profile.glossary.items()) or "-"
        prompt = _PROMPT.format(language=self._profile.name, glossary=glossary, task=task,
                                item=item)
        return ask_json(self._client, self._model, prompt, _Reply, "note", 600)

    def _note(self, kind: str, subject_id: int, task: str, item: str) -> Note | None:
        try:
            reply = self._ask(task, item)
        except openai.APIError as exc:
            log.warning("note for %s %s failed: %s", kind, subject_id, exc)
            return None
        if reply is None:
            log.warning("note for %s %s: invalid json, skipped", kind, subject_id)
            return None
        return Note(subject_kind=kind, subject_id=subject_id, author=self._model,
                    **reply.model_dump())

    def write(self, items: list[tuple[str, int, str]]) -> list[Note]:
        """items = (kind, id, item text). failed ones are skipped, rerun picks them up"""
        tasks = {"candidate": _CANDIDATE_TASK, "link": _LINK_TASK}
        with ThreadPoolExecutor(self._concurrency) as pool:
            out = pool.map(lambda it: self._note(it[0], it[1], tasks[it[0]], it[2]), items)
            return [n for n in out if n is not None]


def candidate_item(cand) -> str:
    return (f"code: {cand.code or '-'}\ntype guess: {cand.suggested_type.value}\n"
            f"page {cand.source_page}: {cand.text}\nverbatim quote: {cand.source_excerpt}")


def link_item(commitment, evidence) -> str:
    return (f"commitment: {commitment.code or ''} {commitment.title}\n"
            f"evidence from {evidence.url} ({evidence.published_on or 'no date'}):\n"
            f"{evidence.title}\n{evidence.snippet[:1500]}")
