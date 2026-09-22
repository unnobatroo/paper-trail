"""Reset Paper Trail's application state for a clean demo run.

With the default SQLite backend: archives the database file and leaves
reusable caches alone.

  keeps   data/models/                  downloaded language models
  keeps   data/processed/fetched/       fetched page text + embedding cache
  resets  data/processed/paper_trail.db archived next to the original

With SUPABASE_URL + SUPABASE_KEY set: deletes all application rows from
the Postgres tables (documents → budgets), keeps the schema.

Run:  uv run python scripts/reset_demo_state.py
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "processed" / "paper_trail.db"
sys.path.insert(0, str(ROOT / "src"))

# delete order respects foreign keys: children first
TABLES = ["budgets", "links", "evidence", "commitments", "candidates",
          "documents"]


def reset_supabase() -> int:
    from paper_trail.infrastructure.settings import _env_file
    _env_file(ROOT / ".env")
    url = os.environ.get("SUPABASE_URL")
    key = (os.environ.get("SUPABASE_KEY")
           or os.environ.get("SUPABASE_SERVICE_KEY"))
    if not (url and key):
        return -1
    from supabase import create_client
    db = create_client(url, key)
    for table in TABLES:
        db.table(table).delete().neq("id", 0).execute()
    print("Cleared all application rows in Supabase "
          "(schema kept). Caches on disk are untouched.")
    return 0


def reset_sqlite() -> int:
    if not DB.exists():
        print("Nothing to reset — no database yet.")
        return 0
    backup = DB.with_name(f"{DB.stem}.bak-{int(time.time())}{DB.suffix}")
    shutil.move(str(DB), str(backup))
    print(f"Archived {DB.name} -> {backup.name}")
    print("Clean state. The app recreates an empty database on next start;")
    print("model downloads and fetched pages are kept, so the next run is fast.")
    return 0


def main() -> int:
    rc = reset_supabase()
    return rc if rc >= 0 else reset_sqlite()


if __name__ == "__main__":
    sys.exit(main())
