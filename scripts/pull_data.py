"""Pull data out of Supabase Storage into the local data/ dirs — the
inverse of push_data.py, for dev machines and CI that want the real
strategy PDFs (the PDF-dependent tests skip without them).

  <bucket>/*.pdf            →  data/source_documents/
  <bucket>/benchmark/*.jsonl →  data/benchmark/

Usage:  uv run python scripts/pull_data.py
Needs SUPABASE_URL + SUPABASE_KEY (service_role) in the environment or
the repo-root .env.
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

    pdfs = [n for n in store.list() if n.endswith(".pdf")]
    settings.seed_dir.mkdir(parents=True, exist_ok=True)
    for name in pdfs:
        (settings.seed_dir / name).write_bytes(store.read(name) or b"")
        print(f"{name} → {settings.seed_dir}/")

    bench_dir = ROOT / "data" / "benchmark"
    bench = store.list("benchmark")
    if bench:
        bench_dir.mkdir(parents=True, exist_ok=True)
        for name in bench:
            data = store.read(f"benchmark/{name}")
            if data:
                (bench_dir / name).write_bytes(data)
                print(f"benchmark/{name} → {bench_dir}/")

    if not pdfs and not bench:
        print("Bucket is empty — run scripts/push_data.py first.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
