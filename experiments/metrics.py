"""Experiment metrics via ranx + scikit-learn — no hand-rolled math.

ranx's metrics are validated against trec_eval; `compare_runs` adds paired
significance tests for model/reranker bake-offs.
"""

from __future__ import annotations

from ranx import Qrels, Run, evaluate


def _qrels(relevance: dict[tuple[str, str], int]) -> Qrels:
    """{(commitment_id, passage_id): graded relevance} → ranx Qrels."""
    return Qrels({q: dict(v) for q, v in _group(relevance).items()})


def _group(relevance: dict[tuple[str, str], int]) -> dict:
    out: dict[str, dict[str, int]] = {}
    for (q, p), rel in relevance.items():
        out.setdefault(q, {})[p] = rel
    return out


def ranking_report(ranked_by_query: dict[str, list[str]],
                   relevance: dict[tuple[str, str], int],
                   k_list=(1, 3, 5)) -> dict:
    """Aggregate retrieval metrics over queries.

    relevance: {(commitment_id, passage_id): graded relevance}
    """
    metrics = (
        [f"recall@{k}" for k in k_list]
        + [f"precision@{k}" for k in k_list]
        + ["mrr", "ndcg@10"]
    )
    run = Run({q: {p: float(len(r) - i) for i, p in enumerate(r)}
               for q, r in ranked_by_query.items()})
    return evaluate(_qrels(relevance), run, metrics,
                    return_mean=True, make_comparable=True)


def compare_runs(relevance: dict[tuple[str, str], int],
                 runs: dict[str, dict[str, list[str]]],
                 metrics=("recall@5", "ndcg@10", "mrr@10")):
    """Significance-tested comparison of named rankings.

    runs: {name: {query_id: [ranked passage ids]}}
    """
    from ranx import compare
    qrels = _qrels(relevance)
    return compare(
        qrels,
        [Run({q: {p: float(len(r) - i) for i, p in enumerate(r)}
              for q, r in ranked.items()}) for ranked in runs.values()],
        list(metrics),
    )


def classification_report(y_true: list[str], y_pred: list[str]) -> dict:
    from collections import Counter

    from sklearn.metrics import accuracy_score
    from sklearn.metrics import classification_report as _report

    labels = sorted(set(y_true) | set(y_pred))
    rep = _report(y_true, y_pred, labels=labels, output_dict=True,
                  zero_division=0)
    per_class = {
        lab: {"precision": round(rep[lab]["precision"], 3),
              "recall": round(rep[lab]["recall"], 3),
              "f1": round(rep[lab]["f1-score"], 3),
              "support": int(rep[lab]["support"])}
        for lab in labels
    }
    return {
        "accuracy": round(accuracy_score(y_true, y_pred), 4),
        "macro_f1": round(rep["macro avg"]["f1-score"], 4),
        "per_class": per_class,
        "confusion": {
            f"{t}>{p}": n
            for (t, p), n in
            sorted(Counter(zip(y_true, y_pred)).items())
        },
    }
