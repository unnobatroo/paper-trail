from pathlib import Path

import pytest

from paper_trail.repositories.store import EvidenceRepository, PolicyRepository


@pytest.fixture
def db_path(tmp_path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def policy(db_path) -> PolicyRepository:
    return PolicyRepository(db_path)


@pytest.fixture
def evidence(db_path) -> EvidenceRepository:
    return EvidenceRepository(db_path)


@pytest.fixture
def strategy_pdf() -> Path:
    p = Path(__file__).parents[1] / "data" / "source_documents" / (
        "jozsefvaros_klimastrategia_2021.pdf"
    )
    if not p.exists():
        pytest.skip("strategy PDF not downloaded")
    return p
