"""seed the gazetteer with a district's named streets, squares and parks from openstreetmap

  uv run python scripts/ops/seed_gazetteer.py "VIII. kerület"            # sqlite
  PAPER_TRAIL_DATABASE_URL=... uv run python scripts/ops/seed_gazetteer.py "..."   # postgres

data © OpenStreetMap contributors, ODbL 1.0. geometry is kept as geojson for later spatial
use; parcel numbers (hrsz) are not in osm, the evidence pipeline records those as it reads
"""

import json
import sys

import requests

from paper_trail.infrastructure.settings import load

# public instances are often overloaded (502/504), try the next one
OVERPASS = ("https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter",
            "https://overpass.private.coffee/api/interpreter")
# osm tag -> gazetteer kind
_KINDS = {"square": "square", "park": "park", "garden": "park"}


def query(area_name: str) -> str:
    return f"""[out:json][timeout:120];
area["name"="{area_name}"]["boundary"="administrative"]["admin_level"="9"]->.a;
(
  way["highway"]["name"](area.a);
  way["place"="square"]["name"](area.a);
  way["leisure"~"park|garden"]["name"](area.a);
  relation["leisure"="park"]["name"](area.a);
);
out tags geom;"""


def places(area_name: str):
    for url in OVERPASS:
        try:
            resp = requests.post(url, data={"data": query(area_name)}, timeout=180,
                                 headers={"User-Agent": "paper-trail gazetteer seed"})
            resp.raise_for_status()
            break
        except requests.RequestException as exc:
            print(f"{url}: {exc}", file=sys.stderr)
    else:
        raise SystemExit("every overpass instance failed, try again later")
    for el in resp.json()["elements"]:
        tags = el.get("tags", {})
        name = tags.get("name", "").strip()
        if not name:
            continue
        kind = _KINDS.get(tags.get("place") or tags.get("leisure"), "street")
        coords = [[p["lon"], p["lat"]] for p in el.get("geometry", [])]
        geojson = json.dumps({"type": "LineString", "coordinates": coords}) if coords else None
        yield kind, name, f"{el['type']}/{el['id']}", geojson


def main(area_name: str) -> None:
    settings = load()
    if settings.database_url:
        from paper_trail.repositories.postgres.store import PostgresEvidenceRepository
        repo = PostgresEvidenceRepository(settings.database_url)
    else:
        from paper_trail.repositories.sqlite.store import EvidenceRepository
        repo = EvidenceRepository(settings.db_path)
    seen = set()
    for kind, name, osm_id, geojson in places(area_name):
        # one row per name: a street drawn as 12 osm ways is still one street
        if (kind, name) in seen:
            continue
        seen.add((kind, name))
        repo.upsert_place(kind, name, name, area_name, osm_id, geojson, "osm")
    print(f"{len(seen)} places from {area_name}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "VIII. kerület")
