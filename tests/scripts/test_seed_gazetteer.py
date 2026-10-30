"""gazetteer seed writes one row per name into DATABASE_URL"""
import importlib.util
from pathlib import Path

from paper_trail.repositories.store import EvidenceRepository

_spec = importlib.util.spec_from_file_location(
    "seed_gazetteer", Path(__file__).resolve().parents[2] / "scripts" / "ops" / "seed_gazetteer.py")
seed = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seed)


def test_seed_dedupes_ways_of_one_street(dsn, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", dsn)
    # a street drawn as two osm ways + a square, no overpass call
    monkeypatch.setattr(seed, "places", lambda *a: iter([
        ("street", "Bérkocsis utca", "way/1", None),
        ("street", "Bérkocsis utca", "way/2", None),
        ("square", "Kálvária tér", "way/3", None)]))
    seed.main("VIII. kerület")
    assert sorted(EvidenceRepository(dsn).place_names()) == ["Bérkocsis utca", "Kálvária tér"]
    assert "2 places" in capsys.readouterr().out
