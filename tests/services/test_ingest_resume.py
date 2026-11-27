"""ingest checkpoints: a crashed job resumes after its last finished page, a lost lease stops it"""

from types import SimpleNamespace

import pytest

from paper_trail.domain.enums import CandidateType
from paper_trail.domain.models import DocumentPage, PolicyCandidate, SourceDocument
from paper_trail.jobs.postgres import PostgresJobRunner, PostgresWorker
from paper_trail.maintenance import reset
from paper_trail.ml.extraction import NoExtractor
from paper_trail.repositories.store import PolicyRepository
from paper_trail.services.ingestion_service import IngestionService

PAGES = [DocumentPage(page_number=n, text=f"Intro. Plant {n}00 trees by 2030.")
         for n in (1, 2, 3, 4)]
PARSER = SimpleNamespace(pages=lambda _: PAGES)


class PageExtractor:
    """one window per page, one candidate quoting it. records which pages it was asked"""

    def __init__(self, name="llm:stub", crash_on=None, on_call=lambda: None):
        self.name, self.crash_on, self.on_call = name, crash_on, on_call
        self.calls: list[list[int]] = []

    def extract_windows(self, pages):
        for p in pages:
            self.calls.append([p.page_number])
            self.on_call()
            if p.page_number == self.crash_on:
                raise RuntimeError("worker killed")
            yield [p], [PolicyCandidate(
                document_id=0, suggested_type=CandidateType.TARGET,
                text=f"Plant {p.page_number}00 trees", normalized_title="Trees",
                source_page=p.page_number, source_excerpt=p.text.split(". ")[1])]


def _ingest(repo, extractor, **kw):
    return IngestionService(repo, extractor, parser=PARSER).ingest(b"pdf", "Strategy", "City",
                                                                   **kw)


def test_crashed_ingest_resumes_after_the_last_finished_page(dsn, worker_dsn, policy):
    worker = PolicyRepository(worker_dsn)  # same grants as the prod worker
    first = PageExtractor(crash_on=3)
    with pytest.raises(RuntimeError, match="worker killed"):
        _ingest(worker, first)
    [doc] = policy.documents()
    assert first.calls == [[1], [2], [3]]
    assert sorted(c.source_page for c in policy.candidates()) == [1, 2]
    assert policy.ingested_pages(doc.id, "llm:stub") == {1, 2}

    retry, progress = PageExtractor(), []
    assert _ingest(worker, retry, on_progress=progress.append) == (doc.id, 2)
    assert retry.calls == [[3], [4]]  # pages 1-2 never go back to the model
    assert progress == ["page 2/4", "page 3/4", "page 4/4"]
    assert sorted(c.source_page for c in policy.candidates()) == [1, 2, 3, 4]

    # a different model hasn't read anything yet
    other = PageExtractor(name="llm:other")
    _ingest(worker, other)
    assert other.calls == [[1], [2], [3], [4]]

    # reset drops generated candidates, so their checkpoints go with them
    reset(dsn, cache=False, everything=False, yes=True)
    assert policy.ingested_pages(doc.id, "llm:stub") == set()


def test_no_llm_records_the_document_and_its_pages(policy):
    doc_id, n = _ingest(policy, NoExtractor())
    assert n == 0 and policy.candidates() == []
    # an llm configured later is another extractor, these don't hide its pages
    assert policy.ingested_pages(doc_id, "none") == {1, 2, 3, 4}


def test_ingest_stops_when_the_job_lease_is_stolen(dsn, policy):
    queue = PostgresJobRunner(dsn)
    job = queue.submit("ingest")
    # the first model call loses the lease, as when a stalled worker gets recovered
    extractor = PageExtractor(on_call=lambda: queue._exec(
        "UPDATE jobs SET lease_token='stolen' WHERE id=:id", id=job.id))

    PostgresWorker(dsn, {"ingest": lambda _payload, progress: _ingest(
        policy, extractor, on_progress=progress)}).run_once()
    [doc] = policy.documents()
    # page 1 committed with its checkpoint, then progress() raised and nothing else ran
    assert extractor.calls == [[1]]
    assert policy.ingested_pages(doc.id, "llm:stub") == {1}
    assert queue.get(job.id).status == "running"  # the new owner's job, untouched


def test_a_slow_page_doesnt_idle_the_other_model_slots(policy):
    """2 in flight: page 3 goes out as soon as page 2 is back, not after slow page 1.
    a batch barrier (pages 1+2, then 3+4) would hold page 3 until page 1 returned"""
    import threading

    from paper_trail.ml.extraction import LLMExtractor
    from tests.profiles import HU
    third_sent = threading.Event()

    def create(messages, **_):
        prompt = messages[0]["content"]
        if "--- page 3 ---" in prompt:
            third_sent.set()
        if "--- page 1 ---" in prompt:
            assert third_sent.wait(5), "page 3 waited for page 1"
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content='{"items": []}'))])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    _ingest(policy, LLMExtractor(client, "m", HU, window=1, concurrency=2))
    [doc] = policy.documents()
    assert policy.ingested_pages(doc.id, "llm:m") == {1, 2, 3, 4}


def test_pages_without_text_are_not_checkpointed_so_a_later_ocr_can_read_them(policy):
    pages = [PAGES[0], DocumentPage(page_number=2, text="  "), PAGES[2]]
    extractor = PageExtractor()
    doc_id, found = IngestionService(
        policy, extractor, parser=SimpleNamespace(pages=lambda _: pages)).ingest(
        b"pdf", "Strategy", "City")
    assert extractor.calls == [[1], [3]]  # the blank page never reaches the model
    assert policy.ingested_pages(doc_id, "llm:stub") == {1, 3}
    assert found == 2


def test_a_revised_pdf_at_the_same_url_is_read_again_but_the_same_bytes_are_not(policy):
    def ingest(content, extractor):
        return IngestionService(policy, extractor, parser=PARSER).ingest(
            content, "Strategy", "City", url="https://city.example/strategy.pdf")

    first = PageExtractor()
    doc_id, _ = ingest(b"pdf v1", first)
    assert first.calls == [[1], [2], [3], [4]]

    same = PageExtractor()
    assert ingest(b"pdf v1", same)[0] == doc_id
    assert same.calls == []  # nothing changed, nothing to read

    revised = PageExtractor()
    assert ingest(b"pdf v2, pages corrected", revised)[0] == doc_id  # same document row
    assert revised.calls == [[1], [2], [3], [4]]  # but the new bytes need reading
    # the old candidates keep their rows: receipts dedupe, so nothing is stored twice
    assert sorted(c.source_page for c in policy.candidates()) == [1, 2, 3, 4]


def test_checkpoints_from_before_content_versioning_still_count(policy):
    doc_id = policy.add_document(SourceDocument(title="Strategy", publisher="City"))
    policy.add_page_candidates(doc_id, "llm:stub", "", [1, 2], [])  # pre-018 rows: no digest
    extractor = PageExtractor()
    IngestionService(policy, extractor, parser=PARSER).ingest(b"anything", "Strategy", "City")
    assert extractor.calls == [[3], [4]]
