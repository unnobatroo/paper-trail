"""grader agreement on filled-in sheets"""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "label_agreement",
    Path(__file__).resolve().parents[2] / "scripts" / "ml" / "label_agreement.py")
agree = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(agree)

SHEET = """# header
=== 1. c1 / e1 ===
PASSAGE:
grade: 3 (sure)
note:

=== 2. c1 / e2 ===
you: 0

=== 3. c2 / e3 ===
grade:
"""


def test_read_sheet_skips_blank_grades(tmp_path):
    path = tmp_path / "anna.txt"
    path.write_text(SHEET)
    assert agree.read_sheet(path) == {("c1", "e1"): 3, ("c1", "e2"): 0}


def test_kappa():
    assert agree.kappa([1, 0, 1, 0], [1, 0, 1, 0]) == 1.0
    assert agree.kappa([1, 1, 0, 0], [1, 0, 1, 0]) == 0.0
    assert agree.kappa([1, 1], [1, 1]) is None


def test_compare_binary_counts_two_and_up():
    a = {("q", "x"): 2, ("q", "y"): 0, ("q", "z"): 1}
    b = {("q", "x"): 3, ("q", "y"): 1, ("q", "w"): 2}
    got = agree.compare(a, b)
    assert got["pairs"] == 2 and got["exact"] == 0.0 and got["binary"] == 1.0
