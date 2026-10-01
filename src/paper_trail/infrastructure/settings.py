"""Runtime configuration — everything has an offline-friendly default.

Backed by pydantic-settings: env vars win, then a gitignored `.env` at the
repo root (see .env.example). Unknown keys are ignored.

Environment overrides:
  PAPER_TRAIL_DB            SQLite path (default data/processed/paper_trail.db)
  PAPER_TRAIL_EMBED_MODEL   fastembed model name
                            (default paraphrase-multilingual-MiniLM-L12-v2;
                            "hashing" for fully offline runs)
  PAPER_TRAIL_RERANKER      "auto" (default — hosted Jina when JINA_API_KEY
                            is set, else none), "none", "jina", or a local
                            cross-encoder model name
  PAPER_TRAIL_RERANK_K      candidates sent to the reranker (default 20)
  PAPER_TRAIL_MAX_DOC_CHARS emergency document bound (default 4_000_000;
                            hitting it truncates and warns, never silently)
  PAPER_TRAIL_SEARCH        "ddgs" | "fixture"  (default ddgs, falls back)
  PAPER_TRAIL_LLM_BASE_URL  OpenAI-compatible endpoint (e.g. Ollama, HF, vLLM)
  PAPER_TRAIL_LLM_API_KEY   API key for that endpoint
  PAPER_TRAIL_LLM_MODEL     model name for structured extraction
  SUPABASE_URL + SUPABASE_KEY
                          when both are set, the app stores state in
                          Supabase/Postgres instead of the local SQLite file
  JINA_API_KEY              enables the hosted Jina reranker under the
                            default "auto" mode; set
                            PAPER_TRAIL_EMBED_MODEL=jina to also use
                            Jina for embeddings
  HF_TOKEN                  enables machine translation in the UI
                            (Helsinki-NLP opus-mt-{lang}-en)
  PAPER_TRAIL_LANGUAGE      language profile for the deterministic parsers
                            — money/date/status cues, stemming, extraction
                            labels (default "hu"; profiles in ml/lang.py)
  PAPER_TRAIL_ALLOWED_DOMAINS
                            comma-separated extra evidence domains, on top
                            of the official_sources registry hosts
  PAPER_TRAIL_MT_MODEL      translation model (default derived from the
                            language profile)
  PAPER_TRAIL_BASELINE_YEAR the year the tracked strategy was adopted —
                            evidence published earlier is forced to
                            background (default: derived from the document
                            URL's /YYYY/MM/ segment, else off)
  PAPER_TRAIL_STORAGE_BUCKET
                            Supabase Storage bucket for source PDFs
                            (default "source-documents")
  PAPER_TRAIL_API_ORIGINS   comma-separated CORS origins for the API
                            (default http://localhost:3000)
"""

from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from ..ml.embeddings import DEFAULT_EMBED_MODEL

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_path: Path = Field(
        default=PROJECT_ROOT / "data" / "processed" / "paper_trail.db",
        validation_alias="PAPER_TRAIL_DB")
    embed_model: str = Field(
        default=DEFAULT_EMBED_MODEL, validation_alias="PAPER_TRAIL_EMBED_MODEL")
    # "auto" = hosted Jina when JINA_API_KEY is set, else embedding-only
    reranker_model: str = Field(
        default="auto", validation_alias="PAPER_TRAIL_RERANKER")
    rerank_candidates: int = Field(
        default=20, validation_alias="PAPER_TRAIL_RERANK_K")
    max_doc_chars: int = Field(
        default=4_000_000, validation_alias="PAPER_TRAIL_MAX_DOC_CHARS")
    search_provider: str = Field(
        default="ddgs", validation_alias="PAPER_TRAIL_SEARCH")
    llm_base_url: str | None = Field(
        default=None, validation_alias="PAPER_TRAIL_LLM_BASE_URL")
    llm_api_key: str | None = Field(
        default=None, validation_alias="PAPER_TRAIL_LLM_API_KEY")
    llm_model: str = Field(
        default="", validation_alias="PAPER_TRAIL_LLM_MODEL")
    fixture_dir: Path = PROJECT_ROOT / "data" / "fixtures"
    seed_dir: Path = PROJECT_ROOT / "data" / "source_documents"
    # stable on-disk model cache — fastembed's default is $TMPDIR,
    # which macOS cleans and which broke downloaded models
    model_cache: Path = Field(
        default=PROJECT_ROOT / "data" / "models",
        validation_alias="PAPER_TRAIL_MODEL_CACHE")
    supabase_url: str | None = Field(
        default=None, validation_alias="SUPABASE_URL")
    supabase_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SUPABASE_KEY", "SUPABASE_SERVICE_KEY"))
    storage_bucket: str = Field(
        default="source-documents",
        validation_alias="PAPER_TRAIL_STORAGE_BUCKET")
    api_origins_raw: str = Field(
        default="http://localhost:3000",
        validation_alias="PAPER_TRAIL_API_ORIGINS")
    baseline_year: int | None = Field(
        default=None, validation_alias="PAPER_TRAIL_BASELINE_YEAR")
    language: str = Field(
        default="hu", validation_alias="PAPER_TRAIL_LANGUAGE")
    allowed_domains_raw: str = Field(
        default="", validation_alias="PAPER_TRAIL_ALLOWED_DOMAINS")
    mt_model: str | None = Field(
        default=None, validation_alias="PAPER_TRAIL_MT_MODEL")
    deployment: str = Field(
        default="", validation_alias="PAPER_TRAIL_DEPLOYMENT")

    @property
    def allowed_domains(self) -> tuple[str, ...]:
        return tuple(d.strip().lower() for d in
                     self.allowed_domains_raw.split(",") if d.strip())

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_base_url and self.llm_model)

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)

    @property
    def api_origins(self) -> list[str]:
        return [o.strip() for o in self.api_origins_raw.split(",")
                if o.strip()]


def load() -> Settings:
    return Settings()
