"""vector width and cache keys for the pgvector index"""

from __future__ import annotations

import hashlib

# pgvector column width, shorter vectors get zero-padded (cosine doesn't care)
VECTOR_DIM = 1024


def fit_vector(vec: list[float], dim: int = VECTOR_DIM) -> list[float]:
    """pad to the column width, wider vectors can't be stored so blow up loudly"""
    if len(vec) > dim:
        raise ValueError(
            f"embedding has {len(vec)} dims, the pgvector column holds {dim}: "
            "use a model with <= 1024 dims or widen the column")
    return vec + [0.0] * (dim - len(vec))


def content_key(model: str, chunk_size: int, text: str) -> str:
    """key for a doc's chunk vectors: new model, chunk size or text = recompute"""
    return hashlib.sha256(
        f"structure-v2|{model}|{chunk_size}|{text}".encode()).hexdigest()[:24]
