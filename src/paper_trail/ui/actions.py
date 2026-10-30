"""what the ui reads and does. goes through the rest api's own router functions, so
validation, 404/422 rules and note joins live in one place. no nicegui in here"""

from __future__ import annotations

import hmac
from dataclasses import dataclass, field

from fastapi import HTTPException

from ..api.deps import get_jobs, get_state
from ..api.routers import candidates as cand_api
from ..api.routers import commitments as com_api
from ..api.routers import documents as doc_api
from ..api.routers import links as link_api
from ..api.routers import trail as trail_api
from ..api.schemas import (
    AcceptCandidateRequest,
    BulkCandidatesRequest,
    BulkLinksRequest,
    IngestRequest,
    JurisdictionRequest,
    LinkDecisionRequest,
)
from ..domain.enums import CandidateType, Jurisdiction, RelationshipType
from ..domain.models import Commitment
from .workspace import Row, build_rows

NEEDS_KEY = "this deployment requires a review key for changes"


class ActionError(Exception):
    """what the reviewer sees in the toast"""


@dataclass
class Snapshot:
    rows: list[Row]
    commitments: list[Commitment]
    doc_urls: dict[int, str] = field(default_factory=dict)
    documents: int = 0


def load() -> Snapshot:
    state = get_state()
    coms = com_api.commitments(state)
    docs = doc_api.documents(state)
    rows = build_rows(cand_api.candidates(None, state), coms,
                      link_api.links(None, None, True, state), trail_api.trail(state))
    return Snapshot(rows, coms, {d.id: d.url for d in docs if d.url}, len(docs))


def review_required() -> bool:
    return bool(get_state().settings.review_key)


def key_ok(given: str | None) -> bool:
    key = get_state().settings.review_key
    return not key or hmac.compare_digest((given or "").encode(), key.encode())


def _write(key: str | None, fn, *args):
    # same shared-secret gate as the api's x-review-key header
    if not key_ok(key):
        raise ActionError(NEEDS_KEY)
    try:
        return fn(*args)
    except HTTPException as exc:
        raise ActionError(str(exc.detail)) from exc


def accept(key, candidate_id: int, kind: str | None = None, title: str | None = None,
           parent_id: int | None = None) -> int:
    req = AcceptCandidateRequest(kind=CandidateType(kind) if kind else None,
                                 title=title, parent_id=parent_id)
    return _write(key, cand_api.accept, candidate_id, req, get_state())["commitment_id"]


def reject(key, candidate_id: int) -> None:
    _write(key, cand_api.reject, candidate_id, get_state())


def bulk_candidates(key, accept_ids: list[int], reject_ids: list[int]) -> dict:
    req = BulkCandidatesRequest(accept=accept_ids, reject=reject_ids)
    return _write(key, cand_api.bulk, req, get_state())


def decide_link(key, link_id: int, accept_it: bool, relationship: str | None = None) -> None:
    req = LinkDecisionRequest(decision="accept" if accept_it else "reject",
                              relationship=RelationshipType(relationship)
                              if accept_it and relationship else None)
    _write(key, link_api.decide, link_id, req, get_state())


def bulk_links(key, accept_ids: list[int], reject_ids: list[int]) -> dict:
    return _write(key, link_api.bulk, BulkLinksRequest(accept=accept_ids, reject=reject_ids),
                  get_state())


def link_detail(link_id: int):
    return link_api.link(link_id, get_state())


def set_jurisdiction(key, commitment_id: int, jurisdiction: str) -> None:
    _write(key, com_api.set_jurisdiction, commitment_id,
           JurisdictionRequest(jurisdiction=Jurisdiction(jurisdiction)), get_state())


def find_evidence(key, commitment_id: int) -> str:
    return _write(key, com_api.find_evidence, commitment_id, get_state(), get_jobs()).id


def available_documents() -> list[str]:
    return doc_api.available(get_state())


def ingest(key, name: str, title: str, publisher: str, url: str = "") -> str:
    req = IngestRequest(name=name, title=title, publisher=publisher, url=url)
    return _write(key, doc_api.ingest, req, get_state(), get_jobs()).id


def job(job_id: str):
    return get_jobs().get(job_id)


def active_jobs(kind: str) -> list[str]:
    return [j.id for j in get_jobs().active(kind)]


def deployment() -> str:
    return get_state().settings.deployment


def glossary() -> dict[str, str]:
    return get_state().profile.glossary


def language_name() -> str:
    p = get_state().profile
    return p.name if p.status_rules else ""
