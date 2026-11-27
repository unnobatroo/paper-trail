"""The review workspace: every commitment with what needs doing next, filtered on the server."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ...bootstrap import AppState
from ...services.workspace_service import build_rows, matches_filter, stage_counts
from ..deps import get_state
from ..schemas import WorkspaceOut, WorkspaceRow
from . import candidates, commitments, documents, links, trail

router = APIRouter(prefix="/api/workspace", tags=["workspace"])


@router.get("")
def workspace(stage: str = "all", kind: str = Query("all", alias="type"), q: str = "",
              state: AppState = Depends(get_state)) -> WorkspaceOut:
    """Return the commitments that match the stage, type and search filters.

    `stage_counts` covers every commitment, so the stage buttons keep their numbers while
    you filter.
    """
    coms = commitments.commitments(state)
    rows = build_rows(candidates.candidates(None, state), coms,
                      links.links(None, None, True, state), trail.trail(state))
    shown = [r for r in rows if matches_filter(r, stage, kind, q)]
    return WorkspaceOut(
        rows=[WorkspaceRow(**vars(r)) for r in shown],
        stage_counts=stage_counts(rows),
        commitments=coms,
        documents={d.id: d.url for d in documents.documents(state) if d.url})
