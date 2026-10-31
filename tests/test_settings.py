import pytest
from pydantic import ValidationError

from paper_trail.settings import Settings


def config(**overrides):
    values = dict(_env_file=None, APP_ENV="production",
        DATABASE_URL="postgresql://user:pass@db/paper_trail",
        JOB_MODE="external", REVIEW_KEY="x" * 32,
        EMBED_MODEL="openai:Qwen/Qwen3-Embedding-0.6B",
        EMBED_BASE_URL="https://goethe:8443/v1",
        RERANKER="none")
    values.update(overrides)
    return Settings(**values)


@pytest.mark.parametrize("bad", [
    {"REVIEW_KEY": ""}, {"JOB_MODE": "internal"},
    {"DATABASE_URL": "mysql://x/y"},
    {"EMBED_BASE_URL": "file:///tmp/model"},
    {"RERANKER": "goethe"},  # no rerank url
])
def test_production_fails_closed(bad):
    with pytest.raises(ValidationError):
        config(**bad)


def test_production_configuration():
    assert config().environment == "production"
