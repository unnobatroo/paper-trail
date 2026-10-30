"""cross-encoder reranking via any /rerank server, stage 2 of retrieval"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod

from .client import model_client


class Reranker(ABC):
    name: str

    @abstractmethod
    def score(self, query: str, passages: list[str]) -> list[float]:
        """one score per passage. rank by it, don't threshold it"""


class HttpReranker(Reranker):
    def __init__(self, client, model: str = "BAAI/bge-reranker-v2-m3",
                 batch_size: int = 2):
        if batch_size < 1:
            raise ValueError("rerank batch size must be positive")
        self.name, self._client, self._batch = model, client, batch_size

    def score(self, query: str, passages: list[str]) -> list[float]:
        scores = []
        for i in range(0, len(passages), self._batch):
            batch = passages[i:i + self._batch]
            # not in the openai api proper, so the sdk's raw post
            body = self._client.post("/rerank", cast_to=object, body={
                "model": self.name, "query": query, "documents": batch, "top_n": len(batch),
                "return_documents": False})
            # infinity/cohere wrap rows in "results", sglang sends a bare list with "score"
            rows = sorted(body["results"] if isinstance(body, dict) else body,
                          key=lambda r: r["index"])
            if [r["index"] for r in rows] != list(range(len(batch))):
                raise ValueError("reranker returned invalid passage indices")
            values = [float(r.get("relevance_score", r.get("score"))) for r in rows]
            if not all(map(math.isfinite, values)):
                raise ValueError("reranker returned nonfinite scores")
            scores += values
        return scores


def get_reranker(kind: str, base_url: str | None, api_key: str | None, model: str,
                 batch_size: int) -> Reranker | None:
    """"none" keeps the embedding order, anything else talks to the /rerank server"""
    if kind in ("", "none", "off"):
        return None
    return HttpReranker(model_client(base_url, api_key), model, batch_size)
