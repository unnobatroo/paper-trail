"""Push local data into Supabase Storage — the repo carries no data files.

Uploads:
  data/source_documents/*       →  <bucket>/<name>   (any document type)
  data/benchmark/* + raw/       →  <bucket>/benchmark/<name>
    (generated *.jsonl plus the authored spec.json)

Usage:  uv run python scripts/push_data.py
Needs SUPABASE_URL + SUPABASE_KEY (service_role) in the environment or the
repo-root .env, and migration 002 applied (creates the bucket).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from paper_trail.infrastructure.settings import load
from paper_trail.sources.document_store import StorageDocumentStore

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    settings = load()
    if not settings.supabase_configured:
        print("SUPABASE_URL / SUPABASE_KEY are not set — nothing to do.")
        return 1

    store = StorageDocumentStore(
        settings.supabase_url, settings.supabase_key,
        bucket=settings.storage_bucket)

    uploaded = 0
    for p in sorted(settings.seed_dir.iterdir()):
        if not p.is_file():
            continue
        store.write(p.name, p.read_bytes())
        print(f"{p.name} → {settings.storage_bucket}/{p.name} "
              f"({p.stat().st_size // 1024} KB)")
        uploaded += 1

    bench = ROOT / "data" / "benchmark"
    for p in sorted(bench.iterdir()) + sorted(
            (bench / "raw").glob("*.txt") if (bench / "raw").exists() else []):
        if not p.is_file():
            continue
        key = f"benchmark/raw/{p.name}" if p.parent.name == "raw" \
            else f"benchmark/{p.name}"
        store.write(key, p.read_bytes())
        print(f"{key} → {settings.storage_bucket}/{key}")
        uploaded += 1

    if not uploaded:
        print("Nothing to push — no PDFs in data/source_documents/ and "
              "nothing in data/benchmark/.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
