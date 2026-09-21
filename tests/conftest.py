import sqlite3
from pathlib import Path

import pytest

from paper_trail.infrastructure.database import connect
from paper_trail.repositories.store import EvidenceRepository, PolicyRepository


@pytest.fixture
def conn(tmp_path) -> sqlite3.Connection:
    return connect(tmp_path / "test.db")


@pytest.fixture
def policy(conn) -> PolicyRepository:
    return PolicyRepository(conn)


@pytest.fixture
def evidence(conn) -> EvidenceRepository:
    return EvidenceRepository(conn)


@pytest.fixture
def strategy_pdf() -> Path:
    p = Path(__file__).parents[1] / "data" / "source_documents" / (
        "jozsefvaros_klimastrategia_2021.pdf"
    )
    if not p.exists():
        pytest.skip("strategy PDF not downloaded")
    return p
