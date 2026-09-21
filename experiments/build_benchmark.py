"""Build the labelled benchmark from real Paper Trail sources.

Deterministic: reads data/benchmark/raw/*.txt (fetched official pages) and
the downloaded official PDFs, chunks them, and emits:

  data/benchmark/commitments.jsonl  — the policy commitments we query for
  data/benchmark/passages.jsonl     — the retrieval corpus (real text)
  data/benchmark/labels.jsonl       — curated (commitment, passage) labels

Labels were assigned by a human reading the sources. relevance:
  2 = this passage is real implementation evidence for the commitment
  1 = related / partial / planned — worth a reviewer's attention
  0 = not evidence for this commitment

relationship uses the app's own enum (RelationshipType) — no new labels.

Run:  uv run python experiments/build_benchmark.py
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "src"))
from paper_trail.sources.pdf import read_pages  # noqa: E402

ROOT = pathlib.Path(__file__).parents[1]
RAW = ROOT / "data" / "benchmark" / "raw"
OUT = ROOT / "data" / "benchmark"
CHUNK = 800

# ---------------------------------------------------------------------------
# Commitments — real measures from the Józsefváros Climate Strategy.

COMMITMENTS = [
    {"id": "C1", "code": "A1.1.1",
     "title": "Utca újra-tervezési, zöldítési program",
     "text": "A javasolt utca újra-tervezési program célja, hogy javítsa a "
             "kerületben a közcélú zöldfelületek arányát és elérhetőségét. "
             "Fasorok, többszintű zöldsávok, utcafásítás, zöldterületnövelő "
             "köztérfejlesztés.",
     "source_page": 45},
    {"id": "C2", "code": "A1.1.4",
     "title": "Épületek, belső udvarok zöldítése",
     "text": "Társasházi és intézményi belső udvarok, homlokzatok, gangok "
             "zöldítése, esővíz-visszatartó megoldások támogatása pályázatok "
             "útján.",
     "source_page": 53},
    {"id": "C3", "code": "A1.2.3",
     "title": "Közösségi kertek program kibővítése",
     "text": "A meglévő közösségi kertek hálózatának bővítése, új kertek "
             "létesítése, komposztálási és kertművelési lehetőségek.",
     "source_page": 61},
    {"id": "C4", "code": "A2.1.1",
     "title": "Mozgásra, közösségi tevékenységre csábító közterek kialakítása",
     "text": "Olyan közterek, terek, sétányok kialakítása és megújítása, "
             "amelyek mozgásra, találkozásra, közösségi használatra csábítanak.",
     "source_page": 63},
    {"id": "C5", "code": "A1.2.2",
     "title": "Fogadj örökbe egy fát program",
     "text": "Lakossági és szervezeti örökbefogadás kerületi közterületek, "
             "zöldsávok, fák gondozására pályázati támogatással.",
     "source_page": 58},
    {"id": "C6", "code": "A2.2.2",
     "title": "Biztonságos kerékpáros infrastruktúra fejlesztése",
     "text": "Kerékpáros útvonalak, tárolók, mikromobilitási pontok "
             "kialakítása, kerékpározható utcák.",
     "source_page": 69},
    {"id": "C7", "code": "A1.1.5",
     "title": "Csapadékvíz kezelése",
     "text": "A csapadékvíz helyben tartása, vízáteresztő burkolatok, "
             "esőkertek, vízgyűjtő megoldások a közterületeken.",
     "source_page": 55},
    {"id": "C8", "code": "M1.1.2",
     "title": "Távhőszolgáltatás fejlesztése",
     "text": "A távhőrendszer hatékonyságának és elérhetőségének fejlesztése, "
             "csatlakozási arány növelése a kerületben.",
     "source_page": 31},
]

# (source_key, kind, locator) — raw text file or (pdf, page) pair.
SOURCES = [
    ("rev8_utcafasitas", "raw", "rev8_utcafasitas.txt"),
    ("rev8_deri-miksa", "raw", "rev8_deri-miksa.txt"),
    ("rev8_losonci-ter", "raw", "rev8_losonci-ter.txt"),
    ("rev8_magdolna-kert", "raw", "rev8_magdolna-kert.txt"),
    ("rev8_danko-utca", "raw", "rev8_danko-utca.txt"),
    ("rev8_vigabbutca", "raw", "rev8_vigabbutca.txt"),
    ("rev8_jazminter", "raw", "rev8_jazminter.txt"),
    ("rev8_koris-utca-zolditese", "raw", "rev8_koris-utca-zolditese.txt"),
    ("rev8_nagy-fuvaros-utca-zolditese", "raw",
     "rev8_nagy-fuvaros-utca-zolditese.txt"),
    ("rev8_krudy-maria", "raw", "rev8_krudy-maria.txt"),
    ("reszvetel_2023", "raw", "reszvetel_2023-as-szavazas.txt"),
    ("reszvetel_2024", "raw", "reszvetel_2024-es-szavazas.txt"),
    ("jkit_p13", "jkit", 13),   # Telkes Mária courtyard greening grants
    ("jkit_p14", "jkit", 14),   # adopt-a-public-space grants
    ("jkit_p15", "jkit", 15),   # adopt-a-public-space details
    ("jkit_p45", "jkit", 45),   # attitude-forming programs incl. gardens
    ("jkit_p48", "jkit", 48),   # community composting / Kőris Kert
    ("jkit_p53", "jkit", 53),   # Práter/Tömő street renewal
    ("jkit_p64", "jkit", 64),   # Szerdahelyi utca
    ("jkit_p66", "jkit", 66),   # Palotanegyed + Egészséges utcák
    ("jkit_p73", "jkit", 73),   # zöldsáv maintenance concepts
    ("strat_p11", "strategy", 11),  # background statistics (negative)
    ("strat_p12", "strategy", 12),
    ("strat_p23", "strategy", 23),  # heat-mortality background (negative)
]

JKIT = ROOT / "data" / "source_documents" / "jkit_beszamolo_2023.pdf"
STRATEGY = ROOT / "data" / "source_documents" / "jozsefvaros_klimastrategia_2021.pdf"

_URLS = {
    "rev8_utcafasitas": "https://rev8.hu/utcafasitas/",
    "rev8_deri-miksa": "https://rev8.hu/deri-miksa/",
    "rev8_losonci-ter": "https://rev8.hu/losonci-ter/",
    "rev8_magdolna-kert": "https://rev8.hu/magdolna-kert/",
    "rev8_danko-utca": "https://rev8.hu/danko-utca/",
    "rev8_vigabbutca": "https://rev8.hu/vigabbutca/",
    "rev8_jazminter": "https://rev8.hu/jazminter/",
    "rev8_koris-utca-zolditese": "https://rev8.hu/koris-utca-zolditese/",
    "rev8_nagy-fuvaros-utca-zolditese":
        "https://rev8.hu/nagy-fuvaros-utca-zolditese/",
    "rev8_krudy-maria": "https://rev8.hu/krudy-maria/",
    "reszvetel_2023":
        "https://reszvetel.jozsefvaros.hu/reszveteli-koltsegvetes/2023-as-szavazas/",
    "reszvetel_2024":
        "https://reszvetel.jozsefvaros.hu/reszveteli-koltsegvetes/2024-es-szavazas/",
}

# Curated labels: (commitment, source_key, [chunk ids or None=all],
#                  relevance, relationship, note)
LABELS = [
    # ---- C1 street greening -------------------------------------------------
    ("C1", "rev8_utcafasitas", [0, 2, 3, 4, 5], 2,
     "direct_implementation", "street-tree programme, ~100 trees, per-street plans"),
    ("C1", "rev8_utcafasitas", [1], 1, "related_but_indirect",
     "community event invite about the planting"),
    ("C1", "rev8_danko-utca", [0], 2, "direct_implementation",
     "tree-lined traffic-calmed route; also states 2.5bn Ft grant"),
    ("C1", "rev8_danko-utca", [1], 1, "supporting",
     "public consultation on the plans"),
    ("C1", "rev8_koris-utca-zolditese", [0], 1, "supporting",
     "participatory-budget street greening"),
    ("C1", "rev8_nagy-fuvaros-utca-zolditese", [0, 1], 1, "supporting",
     "planter beds around street trees"),
    ("C1", "rev8_vigabbutca", [0, 4], 1, "supporting",
     "greener, calmer street pilot"),
    ("C1", "reszvetel_2023", [0], 1, "supporting", "Pál utca greening proposal"),
    ("C1", "reszvetel_2023", [1], 2, "supporting",
     "József utca garden/green strip proposals"),
    ("C1", "reszvetel_2023", [3], 2, "supporting",
     "Magdolna utca greening proposal"),
    ("C1", "reszvetel_2024", [2], 2, "supporting",
     "Mária utca greening proposal"),
    ("C1", "reszvetel_2024", [8], 1, "supporting", "park green-surface fix"),
    ("C1", "jkit_p53", None, 2, "direct_implementation",
     "Práter/Tömő renewal: new trees, fasor, wider pavements"),
    ("C1", "jkit_p64", None, 2, "direct_implementation",
     "Szerdahelyi utca tree-care and greening works"),
    ("C1", "jkit_p66", None, 1, "direct_implementation",
     "Palotanegyed tree planting + Healthy Streets call"),
    ("C1", "jkit_p73", None, 1, "supporting",
     "green-strip concepts awaiting permits"),
    # ---- C2 courtyards ------------------------------------------------------
    ("C2", "jkit_p13", None, 2, "direct_implementation",
     "Telkes Mária program: courtyard/façade greening, exact Ft amounts"),
    ("C2", "jkit_p14", None, 0, "probably_unrelated",
     "hard negative: public-space adoption, not buildings"),
    # ---- C3 community gardens ------------------------------------------------
    ("C3", "rev8_magdolna-kert", None, 2, "direct_implementation",
     "Magdolna kert community garden in preparation"),
    ("C3", "reszvetel_2024", [3], 2, "supporting",
     "new community-garden proposal with 30M Ft estimate"),
    ("C3", "jkit_p45", None, 1, "supporting",
     "community events in Grundkert and gardens"),
    ("C3", "jkit_p48", None, 1, "supporting",
     "composting available in Auróra Klímakert and Kőris Kert"),
    ("C3", "rev8_losonci-ter", [0], 0, "probably_unrelated",
     "hard negative: public square, not a garden"),
    # ---- C4 inviting public spaces ------------------------------------------
    ("C4", "rev8_losonci-ter", None, 2, "direct_implementation",
     "Losonci tér renovated 2023: meeting spots, trees, fitness"),
    ("C4", "rev8_jazminter", None, 2, "direct_implementation",
     "Jázmin tér community-planned square with movement zones"),
    ("C4", "rev8_deri-miksa", None, 2, "direct_implementation",
     "Déri Miksa green promenade, completed 2022"),
    ("C4", "rev8_vigabbutca", [0, 4, 6], 1, "supporting",
     "pedestrian-priority pilot and evaluation"),
    ("C4", "rev8_magdolna-kert", [0], 1, "related_but_indirect",
     "open community space as well as a garden"),
    ("C4", "reszvetel_2023", [2], 1, "supporting", "Magdolna minipark proposal"),
    ("C4", "reszvetel_2023", [7], 1, "supporting",
     "Losonci–Práter community space proposal"),
    ("C4", "reszvetel_2024", [8], 1, "supporting", "park green-surface fix"),
    ("C4", "jkit_p53", None, 1, "related_but_indirect",
     "street renewal improved the public realm"),
    # ---- C5 adopt-a-space ----------------------------------------------------
    ("C5", "jkit_p14", None, 2, "direct_implementation",
     "Fogadj örökbe egy közterületet: rounds, sites, Ft amounts"),
    ("C5", "jkit_p15", None, 2, "direct_implementation",
     "adopted sites and tasks listed"),
    ("C5", "jkit_p13", None, 0, "probably_unrelated",
     "hard negative: building greening grants, not adoption"),
    # ---- C6 cycling ----------------------------------------------------------
    ("C6", "rev8_danko-utca", [0], 1, "supporting",
     "planned route also works as a cycle connection"),
    ("C6", "jkit_p53", None, 2, "direct_implementation",
     "two-way cycling + Bubi point on the renewed section"),
    ("C6", "jkit_p66", None, 1, "direct_implementation",
     "cyclability on Békési/Kölcsey streets"),
    ("C6", "rev8_vigabbutca", [1], 1, "supporting",
     "pedestrian/cycle zone concept tested"),
    ("C6", "reszvetel_2024", [4], 0, "probably_unrelated",
     "hard negative: pedestrian crossing, not cycling"),
    # ---- C7 rainwater --------------------------------------------------------
    ("C7", "rev8_nagy-fuvaros-utca-zolditese", [1], 1, "supporting",
     "permeable beds let rain reach tree roots"),
    ("C7", "rev8_magdolna-kert", [3], 1, "supporting",
     "water-wise permaculture design"),
    ("C7", "jkit_p13", None, 1, "supporting",
     "rain-barrel module among Telkes Mária targets"),
    ("C7", "jkit_p53", None, 0, "probably_unrelated",
     "hard negative: paving, not drainage"),
    # ---- C8 district heating --------------------------------------------------
    ("C8", "reszvetel_2023", [3], 1, "related_but_indirect",
     "energy-efficiency awareness item — adjacent, not heating"),
]

# ---------------------------------------------------------------------------


def _chunk(text: str, n: int = CHUNK) -> list[str]:
    text = " ".join(text.split())
    return [text[i: i + n] for i in range(0, len(text), n)]


def main() -> None:
    jkit = read_pages(JKIT)
    strategy = read_pages(STRATEGY)

    passages = []
    for key, kind, loc in SOURCES:
        if kind == "raw":
            text = (RAW / loc).read_text(encoding="utf-8")
            url = _URLS.get(key, "")
        else:
            pages = jkit if kind == "jkit" else strategy
            text = pages[loc - 1].text
            url = ""
        for i, chunk in enumerate(_chunk(text)):
            passages.append({
                "id": f"{key}#{i}", "source": key, "chunk": i,
                "url": url, "text": chunk,
            })

    labels = []
    pid = {p["id"] for p in passages}
    for com, src, idxs, rel, rel_type, note in LABELS:
        targets = ([f"{src}#{i}" for i in idxs] if idxs is not None
                   else [p["id"] for p in passages if p["source"] == src])
        for t in targets:
            if t not in pid:
                raise SystemExit(f"label targets missing passage {t}")
            labels.append({
                "commitment_id": com, "passage_id": t,
                "relevance": rel, "relationship": rel_type, "note": note,
            })

    OUT.mkdir(parents=True, exist_ok=True)
    for name, rows in (
        ("commitments.jsonl", COMMITMENTS),
        ("passages.jsonl", passages),
        ("labels.jsonl", labels),
    ):
        with (OUT / name).open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"{name}: {len(rows)} rows")


if __name__ == "__main__":
    main()
