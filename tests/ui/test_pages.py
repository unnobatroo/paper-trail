import pytest
from fastapi.testclient import TestClient

from paper_trail.domain.enums import CandidateType, ReviewStatus
from paper_trail.domain.models import PolicyCandidate, SourceDocument
from paper_trail.ui import actions
from tests.api.test_api import state  # noqa: F401  same offline AppState the api tests use


@pytest.fixture
def seeded(state):  # noqa: F811
    doc = state.policy.add_document(SourceDocument(title="Klímastratégia", publisher="Kerület",
                                                   url="https://example.hu/ks.pdf"))
    ids = [state.policy.add_candidate(PolicyCandidate(
        document_id=doc, suggested_type=CandidateType.MEASURE, text=t, normalized_title=t,
        source_page=p, source_excerpt=t, excerpt_on_page=True))
        for t, p in (("Fák ültetése a kerületben", 4), ("Napelemek az iskolákon", 7))]
    return state, ids


@pytest.fixture
def ui_client(seeded):
    from paper_trail.ui.main import app
    with TestClient(app) as c:
        yield c


def test_workspace_renders_the_rows(ui_client):
    html = ui_client.get("/").text
    assert "Fák ültetése a kerületben" in html and "Napelemek az iskolákon" in html
    assert "To confirm 2" in html


def test_old_routes_redirect_to_their_stage(ui_client):
    r = ui_client.get("/evidence", follow_redirects=False)
    assert r.status_code in (302, 307) and r.headers["location"] == "/?stage=review"


def test_api_still_served_next_to_the_ui(ui_client):
    assert ui_client.get("/healthz").json() == {"ok": True}
    assert len(ui_client.get("/api/candidates").json()) == 2


def test_actions_go_through_the_api_rules(seeded):
    st, (a, b) = seeded
    cid = actions.accept(None, a, title="Fák ültetése")
    assert st.policy.commitment(cid).title == "Fák ültetése"
    actions.reject(None, b)
    assert st.policy.candidate(b).review_status == ReviewStatus.REJECTED
    # the api's 404 comes back as a readable error, not a crash
    with pytest.raises(actions.ActionError, match="999"):
        actions.reject(None, 999)
    rows = actions.load().rows
    assert {r.stage for r in rows} == {"search", "rejected"}


def test_review_key_gates_every_write(seeded, monkeypatch):
    st, (a, _) = seeded
    monkeypatch.setattr(st.settings, "review_key", "k" * 32)
    with pytest.raises(actions.ActionError, match="review key"):
        actions.accept("wrong", a)
    assert st.policy.candidate(a).review_status == ReviewStatus.UNREVIEWED
    actions.accept("k" * 32, a)
    assert st.policy.candidate(a).review_status == ReviewStatus.ACCEPTED
