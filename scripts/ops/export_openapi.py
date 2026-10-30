"""dump the api's openapi schema, the frontend types get generated from it

  uv run python scripts/ops/export_openapi.py && (cd web && npm run gen:api)
"""

import json
from pathlib import Path

from paper_trail.api.app import app

OUT = Path(__file__).resolve().parents[2] / "web" / "openapi.json"


def schema() -> str:
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"


if __name__ == "__main__":
    OUT.write_text(schema())
    print(f"wrote {OUT}")
