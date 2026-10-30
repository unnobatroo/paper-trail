"""page cache + vector index on postgres + pgvector"""

import pytest

from paper_trail.repositories.indexing import content_key, fit_vector
from paper_trail.repositories.postgres.index import PostgresPageStore, PostgresVectorIndex
from paper_trail.sources.fetch import FetchedPage

PAGE = FetchedPage(url="https://rev8.hu/utcafasitas/", title="Utcafásítás",
                   text="fák és zöldfelületek " * 100)
VECTORS = [("chunk a", [1.0, 0.0]), ("chunk b", [0.0, 1.0])]


def test_page_store_roundtrip(dsn):
    store = PostgresPageStore(dsn)
    assert store.get(PAGE.url) is None
    store.put(PAGE)
    got = store.get(PAGE.url)
    assert got is not None
    assert (got.url, got.title, got.text) == (PAGE.url, PAGE.title, PAGE.text)


def test_vector_index_roundtrip_and_match(dsn):
    PostgresPageStore(dsn).put(PAGE)
    index = PostgresVectorIndex(dsn)
    assert index.get(PAGE, "hashing", 2400) is None
    assert not index.has(PAGE, "hashing", 2400)
    index.put(PAGE, "hashing", 2400, VECTORS)
    # pgvector pads to the column width, the real dims come back first
    assert [(c, v[:2]) for c, v in index.get(PAGE, "hashing", 2400)] == VECTORS
    assert index.has(PAGE, "hashing", 2400)
    # a different model or a changed document must miss the cache
    assert index.get(PAGE, "other-model", 2400) is None
    changed = FetchedPage(PAGE.url, PAGE.title, PAGE.text + " changed")
    assert index.get(changed, "hashing", 2400) is None

    top = index.match([1.0, 0.0], "fák", "hashing", 2400, [PAGE], k=1)
    assert len(top) == 1 and top[0][1] == "chunk a"

    # lexical side can override dense rank: "ültetés" appears only in the
    # middle chunk, whose dense score is second of three
    index.put(PAGE, "hyb", 2400,
              [("fák szakasz", [1.0, 0.0]),
               ("ültetés szakasz", [0.9, 0.1]),
               ("más szakasz", [0.0, 1.0])])
    top = index.match([1.0, 0.0], "ültetés", "hyb", 2400, [PAGE], k=2)
    assert top[0][1] == "ültetés szakasz"
    assert top[1][1] == "fák szakasz"


def test_content_keys_stable():
    assert content_key("m", 2400, "t") != content_key("m", 2400, "t2")


def _commitment(policy) -> int:
    from paper_trail.domain.enums import CandidateType
    from paper_trail.domain.models import Commitment

    return policy.add_commitment(Commitment(kind=CandidateType.MEASURE, title="plant trees"))


def test_rerun_leaves_reviewed_evidence_alone(policy, evidence):
    from paper_trail.domain.enums import ReviewStatus
    from paper_trail.domain.models import EvidenceItem, EvidenceLink

    c = _commitment(policy)

    ev_id = evidence.add_evidence(EvidenceItem(
        commitment_id=c, url="https://jozsefvaros.hu/x", title="t",
        snippet="the quote the reviewer read"))
    link_id = evidence.add_link(EvidenceLink(
        commitment_id=c, evidence_id=ev_id, score=0.7))
    evidence.decide_link(link_id, ReviewStatus.ACCEPTED)

    # a later search finds the same page with different wording and score
    assert evidence.add_evidence(EvidenceItem(
        commitment_id=c, url="https://jozsefvaros.hu/x", title="t",
        snippet="rewritten passage")) == ev_id
    evidence.add_link(EvidenceLink(commitment_id=c, evidence_id=ev_id, score=0.1))

    assert evidence.evidence(ev_id).snippet == "the quote the reviewer read"
    [link] = evidence.links()
    assert link.score == 0.7 and link.review_status == ReviewStatus.ACCEPTED


def test_rerun_refreshes_unreviewed_evidence(policy, evidence):
    from paper_trail.domain.models import EvidenceItem

    c = _commitment(policy)

    ev_id = evidence.add_evidence(EvidenceItem(
        commitment_id=c, url="https://jozsefvaros.hu/y", title="t", snippet="old"))
    evidence.add_evidence(EvidenceItem(
        commitment_id=c, url="https://jozsefvaros.hu/y", title="t", snippet="new"))
    assert evidence.evidence(ev_id).snippet == "new"


def test_fit_vector_rejects_vectors_wider_than_the_column():
    assert len(fit_vector([1.0])) == 1024
    with pytest.raises(ValueError):
        fit_vector([0.1] * 1025)


def test_lexical_side_uses_stored_lemmas_with_an_analyzer(dsn):
    from types import SimpleNamespace

    # fake lemmatizer: "ültetése" and "ültetés" both become "ültet"
    def analyze(text):
        return SimpleNamespace(lemmas=[w[:5] for w in text.lower().split()])

    analyzer = SimpleNamespace(analyze=analyze, _model="fake")
    PostgresPageStore(dsn).put(PAGE)
    index = PostgresVectorIndex(dsn, analyzer=analyzer)
    index.put(PAGE, "lem", 2400, [("fák szakasz", [1.0, 0.0]),
                                  ("ültetése szakasz", [0.9, 0.1]),
                                  ("más szakasz", [0.0, 1.0])])
    top = index.match([1.0, 0.0], "ültetés", "lem", 2400, [PAGE], k=2)
    assert [t for _, t, _ in top] == ["ültetése szakasz", "fák szakasz"]


def test_rerun_refreshes_entities_and_link_features(policy, evidence):
    from paper_trail.domain.models import EvidenceItem, EvidenceLink, MatchFeatures

    c = _commitment(policy)
    ev_id = evidence.add_evidence(EvidenceItem(
        commitment_id=c, url="https://jozsefvaros.hu/z", title="t", organisations=["old"]))
    evidence.add_link(EvidenceLink(commitment_id=c, evidence_id=ev_id, score=0.5))
    # a rerun with another ner provider: new entities, new shared features
    evidence.add_evidence(EvidenceItem(
        commitment_id=c, url="https://jozsefvaros.hu/z", title="t", organisations=["RÉV8"]))
    evidence.add_link(EvidenceLink(
        commitment_id=c, evidence_id=ev_id, score=0.6,
        features=MatchFeatures(semantic_similarity=0.9, shared_organisations=["RÉV8"])))
    assert evidence.evidence(ev_id).organisations == ["RÉV8"]
    [link] = evidence.links()
    assert link.features.semantic_similarity == 0.9
    assert link.features.shared_organisations == ["RÉV8"]
