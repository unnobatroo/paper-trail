"""Write the API's OpenAPI schema, which the frontend's TypeScript types are generated from.

  uv run python scripts/ops/dump_openapi.py frontend/openapi.json
"""

import json
import os
import sys
from pathlib import Path

# The schema needs no database, but settings insist on a URL before the app is built.
os.environ.setdefault("DATABASE_URL", "postgresql://unused@localhost/unused")

from paper_trail.api.app import app  # noqa: E402


def main() -> None:
    """Write the schema to the path given on the command line."""
    Path(sys.argv[1]).write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
