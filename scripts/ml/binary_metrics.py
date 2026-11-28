"""precision, recall and f1 for a yes/no task, shared by the scripts beside this file.

Plain python on purpose: the evaluation runs in the project's env and the detector training in
the gpu env, and only this needs to be in both (scikit-learn isn't in the gpu env).
"""


def prf(gold: list, pred: list) -> dict:
    """counts and scores, unrounded; an empty denominator scores 0"""
    pairs = list(zip(gold, pred, strict=True))
    tp = sum(bool(g) and bool(p) for g, p in pairs)
    fp = sum(bool(p) and not g for g, p in pairs)
    fn = sum(bool(g) and not p for g, p in pairs)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}
