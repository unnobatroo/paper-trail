"""Reset Paper Trail's application state for a clean demo run.

Archives the SQLite database (documents, candidates, commitments,
evidence, links, budgets) and leaves reusable caches alone:

  keeps   data/models/                  downloaded language models
  keeps   data/processed/fetched/       fetched page text + embedding cache
  resets  data/processed/paper_trail.db archived next to the original

Run:  uv run python scripts/reset_demo_state.py
"""

from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "processed" / "paper_trail.db"


def main() -> int:
    if not DB.exists():
        print("Nothing to reset — no database yet.")
        return 0
    backup = DB.with_name(f"{DB.stem}.bak-{int(time.time())}{DB.suffix}")
    shutil.move(str(DB), str(backup))
    print(f"Archived {DB.name} -> {backup.name}")
    print("Clean state. The app recreates an empty database on next start;")
    print("model downloads and fetched pages are kept, so the next run is fast.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
