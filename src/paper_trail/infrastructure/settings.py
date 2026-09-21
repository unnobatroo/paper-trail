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

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_base_url and self.llm_model)


def load() -> Settings:
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
    )
