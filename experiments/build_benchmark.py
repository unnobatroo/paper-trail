"""Build the labelled benchmark from real Paper Trail sources.

Deterministic: reads the authored spec in data/benchmark/spec.json
(commitments, source registry, URLs, curated labels — data lives with the
data, synced to the bucket by scripts/push_data.py), the fetched raw pages
in data/benchmark/raw/*.txt and the downloaded official PDFs; chunks them
and emits:

  data/benchmark/commitments.jsonl  — the policy commitments we query for
  data/benchmark/passages.jsonl     — the retrieval corpus (real text)
  data/benchmark/labels.jsonl       — curated (commitment, passage) labels

Labels were assigned by a human reading the sources. relevance:
  2 = this passage is real implementation evidence for the commitment
  1 = related / partial / planned — worth a reviewer's attention
  0 = not evidence for this commitment

relationship uses the app's own enum (RelationshipType) — no new labels.

Run:  uv run python experiments/build_benchmark.py
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "src"))
from paper_trail.sources.pdf import read_pages

ROOT = pathlib.Path(__file__).parents[1]
RAW = ROOT / "data" / "benchmark" / "raw"
OUT = ROOT / "data" / "benchmark"
CHUNK = 800

def _spec() -> dict:
    path = OUT / "spec.json"
    if not path.exists():
        raise SystemExit(
            f"{path} missing — the benchmark spec lives with the data; "
            "run scripts/pull_data.py to fetch it from the bucket.")
    return json.loads(path.read_text(encoding="utf-8"))


_SPEC = _spec()

# Spec-derived names kept for corpus.py / chunking_study.py.
COMMITMENTS = _SPEC["commitments"]
# (source_key, kind, locator) — raw text file or (pdf, page) pair.
SOURCES = [(s["key"], s["kind"], s["locator"]) for s in _SPEC["sources"]]
_URLS = _SPEC["urls"]
# (commitment, source_key, chunk ids or None=all, relevance,
#  relationship, note)
LABELS = [
    (l["commitment_id"], l["source"], l["chunks"], l["relevance"],
     l["relationship"], l.get("note", ""))
    for l in _SPEC["labels"]
]

_PAGES: dict[str, list] = {}


def pdf_pages(kind: str):
    """Document pages for a spec `documents` kind — the filenames are
    data, declared in spec.json, not code."""
    if kind not in _PAGES:
        rel = _SPEC.get("documents", {}).get(kind)
        if not rel:
            raise SystemExit(
                f"spec.json has no documents[{kind!r}] entry")
        _PAGES[kind] = read_pages(ROOT / "data" / rel)
    return _PAGES[kind]


def _chunk(text: str, n: int = CHUNK) -> list[str]:
    text = " ".join(text.split())
    return [text[i: i + n] for i in range(0, len(text), n)]


def main() -> None:
    passages = []
    for key, kind, loc in SOURCES:
        if kind == "raw":
            text = (RAW / loc).read_text(encoding="utf-8")
            url = _URLS.get(key, "")
        else:
            text = pdf_pages(kind)[loc - 1].text
            url = ""
        for i, chunk in enumerate(_chunk(text)):
            passages.append({
                "id": f"{key}#{i}", "source": key, "chunk": i,
                "url": url, "text": chunk,
            })

    labels = []
    pid = {p["id"] for p in passages}
    for com, src, idxs, rel, rel_type, note in LABELS:
        targets = ([f"{src}#{i}" for i in idxs] if idxs is not None
                   else [p["id"] for p in passages if p["source"] == src])
        for t in targets:
            if t not in pid:
                raise SystemExit(f"label targets missing passage {t}")
            labels.append({
                "commitment_id": com, "passage_id": t,
                "relevance": rel, "relationship": rel_type, "note": note,
            })

    OUT.mkdir(parents=True, exist_ok=True)
    for name, rows in (
        ("commitments.jsonl", COMMITMENTS),
        ("passages.jsonl", passages),
        ("labels.jsonl", labels),
    ):
        with (OUT / name).open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"{name}: {len(rows)} rows")


if __name__ == "__main__":
    main()
