"""helpers every vector index shares: width, lexical scoring, cache keys"""

from __future__ import annotations

import hashlib
import re

import numpy as np
from py_rust_stemmers import SnowballStemmer

# pgvector column width, shorter vectors get zero-padded (cosine doesn't care)
VECTOR_DIM = 1024


def stemmer_for(language: str):
    """word -> stem callable for a snowball language"""
    st = SnowballStemmer(language)
    return getattr(st, "stem_word", None) or st.stemWord


def lexical_scores(query_text: str, texts: list[str],
                   stem, analyzer=None) -> np.ndarray:
    """stemmed bm25 (rank_bm25), the file backend's stand-in for postgres ts_rank"""
    if analyzer is not None:
        docs = [analyzer.analyze(t).lemmas for t in texts]
        query = analyzer.analyze(query_text).lemmas
    else:
        docs = [[stem(w) for w in re.findall(r"\w+", t.lower())] for t in texts]
        query = [stem(w) for w in re.findall(r"\w+", query_text.lower())]
    if not query or not any(docs):
        return np.zeros(len(texts))
    from rank_bm25 import BM25Okapi
    # bm25 idf goes negative for terms in most docs, clip so "more overlap" never scores lower
    return np.maximum(BM25Okapi([d or [""] for d in docs]).get_scores(query), 0.0)


def _norm(s: np.ndarray) -> np.ndarray:
    lo, hi = float(s.min()), float(s.max())
    return (s - lo) / (hi - lo) if hi > lo else np.zeros_like(s)


def fit_vector(vec: list[float], dim: int = VECTOR_DIM) -> list[float]:
    """pad to the column width, wider vectors can't be stored so blow up loudly"""
    if len(vec) > dim:
        raise ValueError(
            f"embedding has {len(vec)} dims, the pgvector column holds {dim}: "
            "use a model with <= 1024 dims or widen the column")
    return pad_vector(vec, dim)


def pad_vector(vec: list[float], dim: int = VECTOR_DIM) -> list[float]:
    """zero-pad to `dim`, longer vectors untouched"""
    if len(vec) >= dim:
        return vec
    return vec + [0.0] * (dim - len(vec))


def url_key(url: str) -> str:
    """short stable key for a url"""
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def content_key(model: str, chunk_size: int, text: str) -> str:
    """key for a doc's chunk vectors: new model, chunk size or text = recompute"""
    return hashlib.sha256(
        f"structure-v2|{model}|{chunk_size}|{text}".encode()).hexdigest()[:24]
