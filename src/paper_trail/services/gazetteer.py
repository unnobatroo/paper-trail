"""parcel numbers + gazetteer names -> street names

contracts say "36542/1 hrsz.", the strategy says "Kálvária tér", the street is what
lets matching connect them
"""

from __future__ import annotations

from ..ml.accountability import PassageAuditor
from ..repositories.ports import EvidenceStore


class PlaceResolver:
    def __init__(self, store: EvidenceStore, auditor: PassageAuditor, min_name_length: int = 5):
        self._store = store
        self._auditor = auditor
        self._min = min_name_length
        self._known: list[str] = []

    def refresh(self) -> None:
        """reload names once per run so a fresh seed shows up"""
        self._known = [n for n in self._store.place_names() if len(n) >= self._min]

    def resolve(self, passage: str, source_url: str, streets: list[str]) -> list[str]:
        """street names for the passage. unknown parcels get recorded unconfirmed with
        the first street in the same passage, a person confirms later
        """
        low = passage.lower()
        out = [name for name in self._known if name.lower() in low]
        for parcel in self._auditor.parcels(passage):
            street = self._store.resolve_parcel(parcel)
            if street is None and streets:
                street = streets[0]
                self._store.record_parcel(parcel, street, source_url)
            if street:
                out.append(street)
        return list(dict.fromkeys(out))
