"""language profiles for tests, from the fixtures (prod loads them from the db)"""
import json
from pathlib import Path

from paper_trail.ml.lang import LanguageProfile

_DIR = Path(__file__).parent / "fixtures" / "profiles"


def load(code: str) -> LanguageProfile:
    return LanguageProfile.from_dict(json.loads((_DIR / f"{code}.json").read_text()))


HU = load("hu")
EN = load("en")
