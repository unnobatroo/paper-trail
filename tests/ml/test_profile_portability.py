"""nothing hungarian should leak into a non-hungarian deployment"""

from paper_trail.ml.accountability import PassageAuditor
from paper_trail.ml.entities import extract_money
from paper_trail.ml.lang import LanguageProfile
from tests.profiles import EN, HU


def test_english_money_is_not_forint():
    rows = extract_money("The council approved a budget of £2.5 million for street trees.", EN)
    assert [(r.currency, r.amount_native, r.amount_huf) for r in rows] == [
        ("GBP", "2500000.0", None)]


def test_hungarian_ids_need_the_hungarian_profile():
    text = "EKR001234562021 szerződés, 36542/1 hrsz."
    assert PassageAuditor(HU).procurement_ids(text) == ["EKR001234562021"]
    assert PassageAuditor(HU).parcels(text) == ["36542/1"]
    assert PassageAuditor(EN).procurement_ids(text) == []
    assert PassageAuditor(EN).parcels(text) == []
    assert PassageAuditor(LanguageProfile.empty()).parcels(text) == []


def test_old_profiles_with_a_word_list_still_load():
    p = LanguageProfile.from_dict({"code": "hu", "name": "Hungarian", "stemmer": "hungarian",
                                   "ts_config": "hungarian", "currency": "HUF",
                                   "currency_words": ["Ft", "forint"]})
    assert p.currency_words == {"Ft": "HUF", "forint": "HUF"}
