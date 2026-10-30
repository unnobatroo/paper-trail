from paper_trail.ml.accountability import PassageAuditor
from paper_trail.services.gazetteer import PlaceResolver
from tests.profiles import HU


class _Store:
    def place_names(self):
        return ["Tompa utca", "Kálvária tér"]

    def resolve_parcel(self, parcel):
        return None

    def record_parcel(self, *a):
        pass


def test_place_names_match_whole_words_only():
    r = PlaceResolver(_Store(), PassageAuditor(HU))
    r.refresh()
    # endings are fine, a longer name that merely contains it isn't
    assert r.resolve("felújítás a Kálvária téren", "u", []) == ["Kálvária tér"]
    assert r.resolve("a Nagytompa utca fásítása", "u", []) == []
