"""reciprocal rank fusion, doesn't care how each provider scales its scores"""
from collections import defaultdict
from collections.abc import Iterable


def reciprocal_rank_fusion(rankings: Iterable[Iterable[int]],
                           constant: int = 60) -> dict[int, float]:
    if constant < 1:
        raise ValueError("RRF constant must be positive")
    scores: dict[int, float] = defaultdict(float)
    for ranking in rankings:
        seen = set()
        for rank, key in enumerate(ranking, 1):
            if key not in seen:
                scores[key] += 1.0 / (constant + rank)
                seen.add(key)
    return dict(scores)
