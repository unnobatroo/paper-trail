"""Push local data into Supabase Storage — the repo carries no data files.

Uploads:
  data/source_documents/*.pdf   →  <bucket>/<name>
  data/benchmark/*.jsonl        →  <bucket>/benchmark/<name>

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
    for p in sorted(settings.seed_dir.glob("*.pdf")):
        store.write(p.name, p.read_bytes())
        print(f"{p.name} → {settings.storage_bucket}/{p.name} "
              f"({p.stat().st_size // 1024} KB)")
        uploaded += 1

    bench = ROOT / "data" / "benchmark"
    for p in sorted(bench.glob("*.jsonl")):
        store.write(f"benchmark/{p.name}", p.read_bytes())
        print(f"{p.name} → {settings.storage_bucket}/benchmark/{p.name}")
        uploaded += 1

    if not uploaded:
        print("Nothing to push — no PDFs in data/source_documents/ and no "
              "JSONL in data/benchmark/.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
