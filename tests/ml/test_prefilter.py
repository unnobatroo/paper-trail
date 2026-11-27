"""page prefilter: scores, and that skipped pages are checkpointed without reaching the model"""

from pathlib import Path

import pytest

from paper_trail.domain.models import DocumentPage
from paper_trail.ml.prefilter import PagePrefilter, PrefilteredExtractor

MODEL = Path(__file__).parents[2] / "src/paper_trail/ml/models/hu_pf1.json"

MEASURE_SHEET = (
    "Közintézmények épületenergetikai korszerűsítése M1 Az intézkedés célja az önkormányzati "
    "épületek korszerűsítése. Kapcsolódás a célkitűzésekhez: Határidő/időtáv: 2022-2025 "
    "Felelős: Önkormányzat Célcsoport: intézmények Finanszírozási igény: 500 M Ft "
    "Lehetséges forrás: KEHOP Plusz, hazai és uniós pályázati források")
ANALYSIS = (
    "Keszthely város lakosságának száma 2018-as év végén 19 289 fő volt (2. ábra). A legutolsó "
    "népszámlálás óta a város lakossága folyamatosan, enyhén csökkenő tendenciát mutat. "
    "2. ábra: Lakónépesség (Forrás: saját szerkesztés a KSH adatai alapján) A lakosság "
    "korösszetételét tekintve a legnagyobb arányban a középkorúak találhatók.")


@pytest.fixture(scope="module")
def prefilter():
    return PagePrefilter.load(MODEL)


def test_measure_sheet_is_kept_and_narrative_is_skipped(prefilter):
    assert prefilter.keep(MEASURE_SHEET)
    assert not prefilter.keep(ANALYSIS)
    assert prefilter.score(MEASURE_SHEET) > prefilter.score(ANALYSIS)


def test_empty_page_does_not_crash(prefilter):
    assert 0 <= prefilter.score("") <= 1


class Recorder:
    name = "llm:test"

    def __init__(self):
        self.seen = []

    def extract_windows(self, pages):
        self.seen += [p.page_number for p in pages]
        for page in pages:
            yield [page], []


def test_skipped_pages_are_checkpointed_but_never_sent_to_the_model(prefilter):
    inner = Recorder()
    extractor = PrefilteredExtractor(inner, prefilter)
    pages = [DocumentPage(page_number=1, text=ANALYSIS),
             DocumentPage(page_number=2, text=MEASURE_SHEET),
             DocumentPage(page_number=3, text=ANALYSIS)]
    windows = list(extractor.extract_windows(pages))
    assert inner.seen == [2]
    assert sorted(p.page_number for window, _ in windows for p in window) == [1, 2, 3]
    assert all(cands == [] for _, cands in windows)


def test_checkpoints_are_per_prefilter(prefilter):
    assert PrefilteredExtractor(Recorder(), prefilter).name == f"llm:test+{prefilter.name}"
