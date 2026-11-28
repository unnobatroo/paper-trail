"""the layers only import downwards (the contract lives in pyproject's [tool.importlinter])"""

from pathlib import Path

from importlinter.cli import lint_imports

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_every_import_contract_is_kept():
    # the config is named, so the test passes from any working directory, not only the root
    assert lint_imports(config_filename=str(PYPROJECT), no_cache=True, no_logo=True) == 0
