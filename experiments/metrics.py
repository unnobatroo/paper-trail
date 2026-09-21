"""Ranking + classification metrics, no dependencies."""

from __future__ import annotations

import math
from collections import Counter


def recall_at_k(ranked: list[str], gold: set[str], k: int) -> float:
    if not gold:
        return 0.0
    return len(set(ranked[:k]) & gold) / len(gold)


def precision_at_k(ranked: list[str], gold: set[str], k: int) -> float:
    if k == 0:
        return 0.0
    return len(set(ranked[:k]) & gold) / k


def mrr(ranked: list[str], gold: set[str]) -> float:
    for i, p in enumerate(ranked, start=1):
        if p in gold:
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranked: list[str], gains: dict[str, int], k: int) -> float:
    dcg = sum(
        gains.get(p, 0) / math.log2(i + 1)
        for i, p in enumerate(ranked[:k], start=1)
    )
    ideal = sorted(gains.values(), reverse=True)[:k]
    idcg = sum(g / math.log2(i + 1) for i, g in enumerate(ideal, start=1))
    return dcg / idcg if idcg else 0.0


def ranking_report(ranked_by_query: dict[str, list[str]],
                   relevance: dict[tuple[str, str], int],
                   k_list=(1, 3, 5)) -> dict:
    """Aggregate retrieval metrics over queries.

    relevance: {(commitment_id, passage_id): graded relevance}
    """
    out = {}
    for k in k_list:
        rs, ps = [], []
        for q, ranked in ranked_by_query.items():
            gold = {p for (c, p), r in relevance.items()
                    if c == q and r >= 1}
            rs.append(recall_at_k(ranked, gold, k))
            ps.append(precision_at_k(ranked, gold, k))
        out[f"recall@{k}"] = round(sum(rs) / len(rs), 4) if rs else 0
        out[f"precision@{k}"] = round(sum(ps) / len(ps), 4) if ps else 0
    mrrs, ndcgs = [], []
    for q, ranked in ranked_by_query.items():
        gold = {p for (c, p), r in relevance.items() if c == q and r >= 1}
        gains = {p: r for (c, p), r in relevance.items() if c == q}
        mrrs.append(mrr(ranked, gold))
        ndcgs.append(ndcg_at_k(ranked, gains, 10))
    out["mrr"] = round(sum(mrrs) / len(mrrs), 4) if mrrs else 0
    out["ndcg@10"] = round(sum(ndcgs) / len(ndcgs), 4) if ndcgs else 0
    return out


def classification_report(y_true: list[str], y_pred: list[str]) -> dict:
    labels = sorted(set(y_true) | set(y_pred))
    per_class = {}
    f1s = []
    for lab in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == lab and p == lab)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != lab and p == lab)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == lab and p != lab)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        per_class[lab] = {"precision": round(prec, 3), "recall": round(rec, 3),
                          "f1": round(f1, 3),
                          "support": sum(1 for t in y_true if t == lab)}
        f1s.append(f1)
    acc = sum(1 for t, p in zip(y_true, y_pred) if t == p) / max(len(y_true), 1)
    return {
        "accuracy": round(acc, 4),
        "macro_f1": round(sum(f1s) / len(f1s), 4),
        "per_class": per_class,
        "confusion": {
            f"{t}>{p}": n
            for (t, p), n in
            sorted(Counter(zip(y_true, y_pred)).items())
        },
    }
