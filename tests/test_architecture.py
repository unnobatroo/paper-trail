"""the layers only import downwards (the contract lives in pyproject's [tool.importlinter])"""

from importlinter.cli import lint_imports


def test_every_import_contract_is_kept():
    assert lint_imports(no_cache=True, no_logo=True) == 0
