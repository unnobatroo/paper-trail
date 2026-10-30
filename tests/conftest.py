"""every test gets its own postgres database, cloned from one migrated template

TEST_DATABASE_URL points at a disposable pgvector server (owner login), e.g.
docker run -d -p 127.0.0.1:55432:5432 -e POSTGRES_USER=paper_trail \\
  -e POSTGRES_PASSWORD=test-only -e POSTGRES_DB=paper_trail pgvector/pgvector:pg16
"""

import os
import subprocess
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest

from paper_trail.repositories.store import EvidenceRepository, PolicyRepository, engine

ROOT = Path(__file__).parents[1]
TEMPLATE = "pt_template"


def _admin_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.exit("set TEST_DATABASE_URL to a throwaway pgvector server", 2)
    return url


def _url_for(dbname: str) -> str:
    return urlunsplit(urlsplit(_admin_url())._replace(path=f"/{dbname}"))


@pytest.fixture(scope="session")
def template_db() -> str:
    """migrate once per run. the api/worker roles the migrations grant to are cluster-wide"""
    with psycopg.connect(_admin_url(), autocommit=True) as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {TEMPLATE} WITH (FORCE)")
        conn.execute(f"CREATE DATABASE {TEMPLATE}")
        for role in ("paper_trail_api", "paper_trail_worker"):
            if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone():
                conn.execute(f"CREATE ROLE {role} LOGIN PASSWORD 'test-only'")
    subprocess.run(["alembic", "-c", "db/alembic.ini", "upgrade", "head"], cwd=ROOT, check=True,
                   env={**os.environ, "DATABASE_URL": _url_for(TEMPLATE)})
    return TEMPLATE


@pytest.fixture
def dsn(template_db):
    name = f"t_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(_admin_url(), autocommit=True) as conn:
        conn.execute(f"CREATE DATABASE {name} TEMPLATE {template_db}")
    url = _url_for(name)
    yield url
    engine(url).dispose()
    with psycopg.connect(_admin_url(), autocommit=True) as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")


@pytest.fixture
def policy(dsn) -> PolicyRepository:
    return PolicyRepository(dsn)


@pytest.fixture
def evidence(dsn) -> EvidenceRepository:
    return EvidenceRepository(dsn)


@pytest.fixture
def strategy_pdf() -> Path:
    p = ROOT / "data" / "source_documents" / "jozsefvaros_klimastrategia_2021.pdf"
    if not p.exists():
        pytest.skip("strategy PDF not downloaded")
    return p
