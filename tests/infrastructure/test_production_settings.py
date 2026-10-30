import pytest
from pydantic import ValidationError

from paper_trail.infrastructure.settings import Settings


def config(**overrides):
    values = dict(_env_file=None, PAPER_TRAIL_ENV="production",
        PAPER_TRAIL_DATABASE_URL="postgresql://user:pass@db/paper_trail",
        PAPER_TRAIL_JOB_MODE="external", PAPER_TRAIL_REVIEW_KEY="x" * 32,
        PAPER_TRAIL_EMBED_MODEL="openai:Qwen/Qwen3-Embedding-0.6B",
        PAPER_TRAIL_EMBED_BASE_URL="https://goethe:8443/v1",
        PAPER_TRAIL_RERANKER="none")
    values.update(overrides)
    return Settings(**values)


@pytest.mark.parametrize("bad", [
    {"PAPER_TRAIL_REVIEW_KEY": ""}, {"PAPER_TRAIL_JOB_MODE": "internal"},
    {"PAPER_TRAIL_DATABASE_URL": "sqlite:///test.db"},
    {"PAPER_TRAIL_EMBED_BASE_URL": "file:///tmp/model"},
    {"PAPER_TRAIL_RERANKER": "goethe"},  # no rerank url
])
def test_production_fails_closed(bad):
    with pytest.raises(ValidationError):
        config(**bad)


def test_production_configuration():
    assert config().environment == "production"
