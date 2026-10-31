"""settings: env vars win, then a gitignored .env. every var is on the wiki (Reference)"""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .ml.embeddings import DEFAULT_EMBED_MODEL

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = Field(
        default="development", validation_alias="APP_ENV")
    # postgres + pgvector, the only store. dev and tests use a throwaway container
    database_url: str = Field(validation_alias="DATABASE_URL")
    process_role: Literal["api", "worker"] = Field(
        default="api", validation_alias="PROCESS_ROLE")
    job_mode: Literal["internal", "external"] = Field(
        default="internal", validation_alias="JOB_MODE")
    parser: Literal["pypdf", "docling"] = Field(
        default="pypdf", validation_alias="PARSER")
    parser_device: Literal["cpu", "cuda"] = Field(
        default="cpu", validation_alias="PARSER_DEVICE")
    nlp: Literal["rules", "huspacy"] = Field(
        default="rules", validation_alias="NLP")
    # who/where/when in passages: gliner on cpu (prod worker, `uv sync --extra ner`),
    # none = bare years only. none by default so a fresh `make setup` just works
    ner: Literal["gliner", "none"] = Field(default="none", validation_alias="NER")
    searxng_url: str | None = Field(default=None, validation_alias="SEARXNG_URL")
    rerank_base_url: str | None = Field(
        default=None, validation_alias="RERANK_BASE_URL")
    rerank_api_key: str | None = Field(
        default=None, validation_alias="RERANK_API_KEY")
    model_ca_bundle: Path | None = Field(
        default=None, validation_alias="MODEL_CA_BUNDLE")
    max_fetch_workers: int = Field(default=2, ge=1, le=8,
                                   validation_alias="FETCH_WORKERS")
    enable_sitemaps: bool = Field(default=False, validation_alias="SITEMAPS")
    document_dir: Path | None = Field(default=None, validation_alias="DOCUMENT_DIR")

    embed_model: str = Field(
        default=DEFAULT_EMBED_MODEL, validation_alias="EMBED_MODEL")
    # endpoint for openai:<model> embeddings
    embed_base_url: str | None = Field(
        default=None, validation_alias="EMBED_BASE_URL")
    embed_api_key: str | None = Field(
        default=None, validation_alias="EMBED_API_KEY")
    # "none" or anything else = the /rerank server at RERANK_BASE_URL
    reranker_model: str = Field(
        default="none", validation_alias="RERANKER")
    # model id the rerank server knows the cross-encoder by
    rerank_model: str = Field(
        default="BAAI/bge-reranker-v2-m3", validation_alias="RERANK_MODEL")
    # ui machine translation, dev only
    hf_token: str | None = Field(default=None, validation_alias="HF_TOKEN")
    rerank_candidates: int = Field(
        default=20, ge=1, le=20, validation_alias="RERANK_K")
    max_doc_chars: int = Field(
        default=4_000_000, validation_alias="MAX_DOC_CHARS")
    search_provider: str = Field(
        default="ddgs", validation_alias="SEARCH_PROVIDER")
    llm_base_url: str | None = Field(
        default=None, validation_alias="LLM_BASE_URL")
    llm_api_key: str | None = Field(
        default=None, validation_alias="LLM_API_KEY")
    llm_model: str = Field(
        default="", validation_alias="LLM_MODEL")
    # pages per llm call, small models want 1
    llm_window_pages: int = Field(
        default=4, ge=1, le=16, validation_alias="LLM_WINDOW")
    # calls in flight, match the model server's max-conc
    llm_concurrency: int = Field(
        default=1, ge=1, le=8, validation_alias="LLM_CONCURRENCY")
    # passages per /rerank call, a gpu box eats the whole top-k at once
    rerank_batch: int = Field(
        default=2, ge=1, le=20, validation_alias="RERANK_BATCH")
    fixture_dir: Path = PROJECT_ROOT / "data" / "fixtures"
    seed_dir: Path = PROJECT_ROOT / "data" / "source_documents"
    # fastembed defaults to $TMPDIR, macos wipes it and the model breaks
    model_cache: Path = Field(
        default=PROJECT_ROOT / "data" / "models",
        validation_alias="MODEL_CACHE")
    # cors for other clients, the ui is same-origin
    api_origins_raw: str = Field(
        default="",
        validation_alias="API_ORIGINS")
    baseline_year: int | None = Field(
        default=None, validation_alias="BASELINE_YEAR")
    language: str = Field(
        default="hu", validation_alias="SOURCE_LANGUAGE")
    allowed_domains_raw: str = Field(
        default="", validation_alias="ALLOWED_DOMAINS")
    mt_model: str | None = Field(
        default=None, validation_alias="MT_MODEL")
    deployment: str = Field(
        default="", validation_alias="DEPLOYMENT")
    review_key: str = Field(
        default="", validation_alias="REVIEW_KEY")

    @model_validator(mode="after")
    def validate_runtime(self):
        for name in ("embed_base_url", "llm_base_url", "searxng_url", "rerank_base_url"):
            value = getattr(self, name)
            if value and (urlsplit(value).scheme not in ("http", "https")
                          or not urlsplit(value).hostname):
                raise ValueError(f"{name} must be an HTTP(S) endpoint")
        if not self.database_url.startswith(("postgresql://", "postgres://")):
            raise ValueError("database_url must use PostgreSQL")
        if self.search_provider == "searxng" and not self.searxng_url:
            raise ValueError("searxng requires SEARXNG_URL")
        if self.reranker_model not in ("", "none", "off") and not self.rerank_base_url:
            raise ValueError("a reranker needs RERANK_BASE_URL")
        if self.environment == "production":
            if self.job_mode != "external":
                raise ValueError("production requires external job workers")
            if self.process_role == "api" and len(self.review_key.strip()) < 32:
                raise ValueError("production requires a review key of at least 32 characters")
            if not self.embed_base_url or not self.embed_model.startswith("openai:"):
                raise ValueError("production requires a configured local embedding endpoint")
        return self

    @property
    def allowed_domains(self) -> tuple[str, ...]:
        return tuple(d.strip().lower() for d in
                     self.allowed_domains_raw.split(",") if d.strip())

    @property
    def translation(self) -> bool:
        # ui reading aid only, never in production where a reviewer needs the source
        return bool(self.hf_token) and self.environment != "production"

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_base_url and self.llm_model)

    @property
    def api_origins(self) -> list[str]:
        return [o.strip() for o in self.api_origins_raw.split(",")
                if o.strip()]


def load() -> Settings:
    return Settings()
