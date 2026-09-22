"""Runtime configuration — everything has an offline-friendly default.

Environment overrides:
  PAPER_TRAIL_DB            SQLite path (default data/processed/paper_trail.db)
  PAPER_TRAIL_EMBED_MODEL   fastembed model name
                            (default intfloat/multilingual-e5-large;
                            "hashing" for fully offline runs)
  PAPER_TRAIL_RERANKER      cross-encoder model name or "none"
                            (default jina-reranker-v2-base-multilingual)
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
  JINA_API_KEY              hosted embeddings/reranking — set
                          PAPER_TRAIL_EMBED_MODEL=jina and
                          PAPER_TRAIL_RERANKER=jina to use it
  HF_TOKEN                  enables Hungarian→English machine translation
                            in the UI (Helsinki-NLP/opus-mt-hu-en)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ..ml.embeddings import DEFAULT_EMBED_MODEL
from ..ml.rerank import DEFAULT_RERANKER

PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Settings:
    db_path: Path
    embed_model: str
    reranker_model: str
    rerank_candidates: int
    max_doc_chars: int
    search_provider: str
    llm_base_url: str | None
    llm_api_key: str | None
    llm_model: str
    fixture_dir: Path
    seed_dir: Path
    model_cache: Path
    supabase_url: str | None
    supabase_key: str | None

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_base_url and self.llm_model)

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)


def _env_file(path: Path) -> None:
    """Read KEY=VALUE lines into os.environ defaults — lets the app run
    from a plain .env without a dotenv dependency."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(),
                              value.strip().strip('"').strip("'"))


def load() -> Settings:
    _env_file(PROJECT_ROOT / ".env")
    return Settings(
        db_path=Path(
            os.environ.get(
                "PAPER_TRAIL_DB", PROJECT_ROOT / "data" / "processed" / "paper_trail.db"
            )
        ),
        embed_model=os.environ.get("PAPER_TRAIL_EMBED_MODEL",
                                   DEFAULT_EMBED_MODEL),
        reranker_model=os.environ.get("PAPER_TRAIL_RERANKER",
                                      DEFAULT_RERANKER),
        rerank_candidates=int(os.environ.get("PAPER_TRAIL_RERANK_K", "20")),
        max_doc_chars=int(
            os.environ.get("PAPER_TRAIL_MAX_DOC_CHARS", "4000000")),
        search_provider=os.environ.get("PAPER_TRAIL_SEARCH", "ddgs"),
        llm_base_url=os.environ.get("PAPER_TRAIL_LLM_BASE_URL"),
        llm_api_key=os.environ.get("PAPER_TRAIL_LLM_API_KEY"),
        llm_model=os.environ.get("PAPER_TRAIL_LLM_MODEL", ""),
        fixture_dir=PROJECT_ROOT / "data" / "fixtures",
        seed_dir=PROJECT_ROOT / "data" / "source_documents",
        # stable on-disk model cache — fastembed's default is $TMPDIR,
        # which macOS cleans and which broke downloaded models
        model_cache=Path(
            os.environ.get("PAPER_TRAIL_MODEL_CACHE",
                           PROJECT_ROOT / "data" / "models")),
        supabase_url=os.environ.get("SUPABASE_URL"),
        supabase_key=(os.environ.get("SUPABASE_KEY")
                      or os.environ.get("SUPABASE_SERVICE_KEY")),
    )
