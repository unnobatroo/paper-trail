"""build the detector's train / val / test files from the labelled passages and pages

train  CPR passages from dev geographies (minus a validation slice) + hand-labelled
       Hungarian pages (Józsefváros, 4 dev towns)
val    15% of the CPR dev geographies, picked by a stable hash, for early stopping
test_cpr   CPR passages from the test geographies (locked: score once)
test_hu    the 3 held-out Hungarian towns (locked: score once)
test_hu2   more random pages from those 3 towns, labelled after test_hu was scored
test_hu_strat  pages from the back of those 3 plans (over-represents measures)
Uncertain pages are dropped everywhere. Rows: {"text", "label", "src"}.

  uv run --with pyarrow python scripts/ml/export_detector_data.py
"""

import hashlib
import json
from pathlib import Path

import pandas as pd

OUT = Path("data/eval_ext/detector")
SILVER = Path("data/eval_ext/silver")
LABELS = ("annotation_NZT", "annotation_Reduction", "annotation_Other")


DEV_TOWNS = {"keszthely", "godollo", "tata", "kecskemet"}
TEST_TOWNS = {"bodajk", "kisber_babolna", "turkeve"}


def bucket(key: str, salt: str) -> int:
    return hashlib.sha256(f"{salt}:{key}".encode()).digest()[0]  # 0..255


def hu_rows(sample_file: str, label_file: str, src: str,
            docs: set[str] | None = None) -> list[dict]:
    sample = json.loads((SILVER / sample_file).read_text(encoding="utf-8"))
    labels = json.loads((SILVER / label_file).read_text(encoding="utf-8"))
    rows = []
    for doc, lab in labels.items():
        if not isinstance(lab, dict) or (docs is not None and doc not in docs):
            continue
        for name, value in (("positive", 1), ("negative", 0)):
            for p in lab[name]:
                rows.append({"text": " ".join(sample[doc][str(p)].split()), "label": value,
                             "src": f"{src}:{doc}:{p}"})
    return rows


def write(name: str, rows: list[dict]) -> None:
    (OUT / f"{name}.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    pos = sum(r["label"] for r in rows)
    print(f"{name}: {len(rows)} rows, {pos} positive")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    d = pd.read_parquet("data/eval_ext/cpr-targets/data/train-00000-of-00001.parquet")
    d["label"] = (d[list(LABELS)].sum(axis=1) > 0).astype(int)
    # same coin as eval_cpr_targets.in_test(seed=13)
    d["test"] = [bucket(g, "13") % 2 == 1 for g in d.geography]
    d["val"] = [bucket(g, "val") < 38 for g in d.geography]  # ~15% of geographies
    rows = lambda f: [{"text": " ".join(t.split()), "label": int(y), "src": f"cpr:{g}"}  # noqa: E731
                      for t, y, g in zip(f.text, f.label, f.geography, strict=True)]
    dev = d[~d.test]
    write("test_cpr", rows(d[d.test]))
    write("val", rows(dev[dev.val]))
    train = (
        rows(dev[~dev.val])
        + hu_rows("sample_jv.json", "labels_jv.json", "hu")
        + hu_rows("sample_hu4.json", "labels_hu4.json", "hu")
        + hu_rows("sample_more.json", "labels_more.json", "hu", DEV_TOWNS)
        + hu_rows("sample_strat.json", "labels_strat.json", "hu", DEV_TOWNS)
    )
    write("train", train)
    write("test_hu", hu_rows("sample_hu3_heldout.json", "labels_hu3_heldout.json", "hu"))
    write("test_hu2", hu_rows("sample_more.json", "labels_more.json", "hu", TEST_TOWNS))
    # drawn from the back of each plan, so the positive rate is not the real one
    write("test_hu_strat", hu_rows("sample_strat.json", "labels_strat.json", "hu", TEST_TOWNS))


if __name__ == "__main__":
    main()
