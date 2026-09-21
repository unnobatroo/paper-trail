"""A small registry of known official documents on the allowed domains.

This is a *source catalogue*, not seeded results: each URL is fetched and read
like any other evidence page, then ranked by the same retrieval pipeline. It
exists because official implementation reports are PDFs that web search does
not always surface well.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OfficialDoc:
    url: str
    title: str
    publisher: str


OFFICIAL_DOCS: list[OfficialDoc] = [
    OfficialDoc(
        url="https://jozsefvaros.hu/downloads/2023/05/jkit-beszamolo-es-intezkedesek-pdf.pdf?ver=20250507093408",
        title="Beszámoló a 2023–2024. évi Józsefvárosi Klímavédelmi Intézkedési Terv megvalósulásáról",
        publisher="Józsefvárosi Önkormányzat",
    ),
    OfficialDoc(
        url="https://jozsefvaros.hu/downloads/2024/03/jozsefvarosi-kornyezetvedelmi-program-2024-2029-pdf.pdf?ver=20240327104125",
        title="Józsefvárosi Környezetvédelmi Program 2024–2029",
        publisher="Józsefvárosi Önkormányzat",
    ),
    OfficialDoc(
        url="https://jozsefvaros.hu/downloads/2022/07/secap_vegleges0711-pdf.pdf?ver=20220726143556",
        title="Józsefváros Fenntartható Energia és Klíma Akcióterv (SECAP)",
        publisher="Józsefvárosi Önkormányzat",
    ),
    OfficialDoc(
        url="https://rev8.hu/utcafasitas/",
        title="Utcafásítás – RÉV8",
        publisher="RÉV8 Zrt.",
    ),
    OfficialDoc(
        url="https://reszvetel.jozsefvaros.hu/reszveteli-koltsegvetes/2024-es-szavazas/",
        title="Részvételi költségvetés – 2024-es szavazás",
        publisher="Józsefvárosi Önkormányzat",
    ),
    OfficialDoc(
        url="https://reszvetel.jozsefvaros.hu/reszveteli-koltsegvetes/2023-as-szavazas/",
        title="Részvételi költségvetés – 2023-as szavazás",
        publisher="Józsefvárosi Önkormányzat",
    ),
]
