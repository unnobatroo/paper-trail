"""Interaction regressions: inspection, selection, provenance and read-only trails."""
from types import SimpleNamespace

from streamlit.testing.v1 import AppTest

from paper_trail.domain.enums import CandidateType, RelationshipType, ReviewStatus
from paper_trail.domain.models import PolicyCandidate, SourceDocument, EvidenceItem, EvidenceLink
from paper_trail.presentation.formatting import display_title, title_groups
from paper_trail.presentation.tracker import _objective_groups
from paper_trail.services.metrics_service import MetricsService
from paper_trail.services.review_service import ReviewService


def _state(policy, evidence):
    doc = policy.add_document(SourceDocument(title="Strategy", publisher="Council"))
    for title, kind, code in [("**Green streets **", CandidateType.OBJECTIVE, "A1"),
                              ("Green streets", CandidateType.OBJECTIVE, "A1"),
                              ("Street planting", CandidateType.MEASURE, "A1.1")]:
        policy.add_candidate(PolicyCandidate(document_id=doc, text=title, normalized_title=title,
            suggested_type=kind, code=code, source_page=20, source_excerpt=title))
    return SimpleNamespace(policy=policy, evidence=evidence,
        review=ReviewService(policy, evidence), metrics=MetricsService(policy, evidence))


def _screen(module, state):
    at = AppTest.from_string(f'''
import streamlit as st
from paper_trail.presentation import {module}
st.session_state["show_en"] = False
{module}.render(st.session_state["_test_state"])
''', default_timeout=15)
    at.session_state['_test_state'] = state
    return at.run()


def test_title_inspects_checkbox_only_selects_and_batch_keeps_sources(policy, evidence):
    state = _state(policy, evidence)
    at = _screen('review_commitments', state)
    assert not at.exception
    assert len(at.checkbox) == 2  # the two exact-title mentions share a row
    at.button(key='hl_c_3').click().run()
    assert at.session_state['detail_id'] == 3
    assert not any(c.value for c in at.checkbox)
    at.checkbox(key='csel_1').check().run()
    assert at.session_state['detail_id'] == 3
    assert len(policy.candidates(ReviewStatus.UNREVIEWED)) == 3
    at.button(key='primary_confirm_c').click().run()
    assert len(policy.candidates()) == 3
    assert len(policy.commitments()) == 2
    assert policy.candidate(3).review_status == ReviewStatus.UNREVIEWED


def test_empty_filter_is_not_finished_review(policy, evidence):
    state = _state(policy, evidence)
    at = _screen('review_commitments', state)
    at.text_input(key='cq').set_value('does not exist').run()
    assert not at.exception
    assert not at.success
    assert any('Nothing matches' in c.value for c in at.caption)
    state.review.confirm_candidates([1, 2, 3])
    at.run()
    assert any('All commitments reviewed' in s.value for s in at.success)
    assert len(at.checkbox) == 0


def test_trail_filter_keeps_child_when_parent_has_no_evidence(policy, evidence):
    state = _state(policy, evidence)
    state.review.confirm_candidates([1, 2, 3])
    child = next(c for c in policy.commitments() if c.code == 'A1.1')
    eid = evidence.add_evidence(EvidenceItem(commitment_id=child.id, url='https://rev8.hu/trees', title='Planting'))
    lid = evidence.add_link(EvidenceLink(commitment_id=child.id, evidence_id=eid))
    state.review.accept_link(lid, RelationshipType.SUPPORTING)
    at = _screen('tracker', state)
    at.session_state['trail_filter'] = 'Has evidence'
    at.run()
    assert not at.exception
    assert not at.checkbox
    assert any(b.label == 'Street planting' for b in at.button)
    assert not any('Confirm' in b.label or 'Reject' in b.label or b.label == 'Clear' for b in at.button)
    groups = title_groups(state.metrics.trail(), lambda r: r.commitment.title, lambda r: r.commitment.kind)
    grouped, by_id = _objective_groups(groups)
    assert len(grouped) == 1
    assert len(by_id) == 3  # both original objective IDs survive


def test_evidence_relationship_survives_inspector_change_and_batch(policy, evidence):
    state = _state(policy, evidence)
    state.review.confirm_candidates([1, 3])
    for com in policy.commitments():
        eid = evidence.add_evidence(EvidenceItem(commitment_id=com.id, url=f'https://rev8.hu/{com.id}', title=f'Source {com.id}'))
        evidence.add_link(EvidenceLink(commitment_id=com.id, evidence_id=eid))
    at = _screen('review_evidence', state)
    assert not at.exception
    at.selectbox(key='rel_1').select(RelationshipType.BUDGET).run()
    at.button(key='hl_e_2').click().run()
    assert not any(c.value for c in at.checkbox)
    at.checkbox(key='lsel_1').check().run()
    at.button(key='primary_link_confirm').click().run()
    assert evidence.link(1).relationship == RelationshipType.BUDGET
    assert evidence.link(2).review_status == ReviewStatus.UNREVIEWED


def test_display_normalization_preserves_meaning():
    assert display_title(' ## **NINCS  UTCA ZÖLD NÉLKÜL ** : ') == 'NINCS UTCA ZÖLD NÉLKÜL'
    assert display_title('500 m / 2030') == '500 m / 2030'


def test_empty_search_enters_review_without_reoffering_same_session(policy, evidence):
    state = _state(policy, evidence)
    state.review.confirm_candidates([3])
    searched = []
    def find(com, progress):
        searched.append(com.id)
        progress('Found 0 official pages to check — reading them…')
        return []
    state.evidence_svc = SimpleNamespace(find_evidence=find, warnings=[])
    state.settings = SimpleNamespace(embed_model='jina', reranker_model='none')
    at = _screen('review_evidence', state)
    com_id = policy.commitments()[0].id
    at.checkbox(key=f'esel_{com_id}').check().run()
    at.button(key='primary_search_go').click().run()
    assert not at.exception
    assert searched == [com_id]
    assert at.session_state['evidence_phase'] == 'Review matches'
    assert not at.checkbox
    at.session_state['evidence_phase'] = 'Choose commitments'
    at.run()
    assert not at.checkbox
    assert any('All commitments searched' in s.value for s in at.success)
