import importlib.util
import json
import sys
from pathlib import Path

from paper_trail.domain.models import DocumentPage

_spec = importlib.util.spec_from_file_location(
    "check_gold", Path(__file__).resolve().parents[2] / "scripts" / "ml" / "check_gold.py")
check_gold = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_gold)


def test_only_verbatim_quotes_and_clean_empty_pages_survive(tmp_path, monkeypatch, capsys):
    pages = [DocumentPage(page_number=1, text="A fák  ültetése 2030-ig.")]
    monkeypatch.setattr(check_gold, "read_pages", lambda _: pages)
    row = {"doc": "a", "pdf": "a.pdf", "page": 1, "title_en": "t"}
    rows = [{**row, "quote": "fák ültetése"},          # whitespace aside, it's there
            {**row, "quote": "   "},                   # blank, "" is in every string
            {**row, "quote": "napelemek"},             # not on the page
            {**row, "empty": True},
            {**row, "empty": True, "quote": "fák"}]    # empty but quoted, contradiction
    src, out = tmp_path / "in.jsonl", tmp_path / "out.jsonl"
    src.write_text("".join(json.dumps(r) + "\n" for r in rows))
    monkeypatch.setattr(sys, "argv", ["x", str(src), "--out", str(out), "--sample", "5"])
    check_gold.main()
    kept = [json.loads(line) for line in out.read_text().splitlines()]
    assert kept == [rows[0], rows[3]]
    # empty labels show up in the spot check too
    assert "CHECK a p1 (nothing to extract)" in capsys.readouterr().out
