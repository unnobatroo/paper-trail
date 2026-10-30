"""the frontend's types are generated from web/openapi.json, it must match the live api"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_openapi_snapshot_is_current():
    spec = importlib.util.spec_from_file_location("export_openapi",
                                                  ROOT / "scripts" / "ops" / "export_openapi.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert (ROOT / "web" / "openapi.json").read_text() == module.schema(), (
        "api changed: run `uv run python scripts/ops/export_openapi.py && "
        "(cd web && npm run gen:api)`")
