"""seed the gazetteer with a district's named streets, squares and parks from openstreetmap

  DATABASE_URL=... uv run python scripts/ops/seed_gazetteer.py "VIII. kerület" --admin-level 9

--admin-level narrows same-named areas: 9 = budapest district, 8 = most towns

data © OpenStreetMap contributors, ODbL 1.0. geometry is kept as geojson for later spatial
use; parcel numbers (hrsz) are not in osm, the evidence pipeline records those as it reads
"""

import argparse
import json
import sys

import requests

from paper_trail.repositories.store import EvidenceRepository
from paper_trail.settings import load

# public instances are often overloaded (502/504), try the next one
OVERPASS = ("https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter",
            "https://overpass.private.coffee/api/interpreter")
# osm tag -> gazetteer kind
_KINDS = {"square": "square", "park": "park", "garden": "park"}


def query(area_name: str, admin_level: int | None = None) -> str:
    level = f'["admin_level"="{admin_level}"]' if admin_level else ""
    return f"""[out:json][timeout:120];
area["name"="{area_name}"]["boundary"="administrative"]{level}->.a;
(
  way["highway"]["name"](area.a);
  way["place"="square"]["name"](area.a);
  way["leisure"~"park|garden"]["name"](area.a);
  relation["leisure"="park"]["name"](area.a);
);
out tags geom;"""


def _geojson(el: dict) -> str | None:
    # relations carry their geometry on the members, closed ways are areas
    if el["type"] == "relation":
        lines = [[[p["lon"], p["lat"]] for p in m.get("geometry", [])]
                 for m in el.get("members", []) if m.get("geometry")]
        return json.dumps({"type": "MultiLineString", "coordinates": lines}) if lines else None
    coords = [[p["lon"], p["lat"]] for p in el.get("geometry", [])]
    if not coords:
        return None
    if len(coords) > 3 and coords[0] == coords[-1]:
        return json.dumps({"type": "Polygon", "coordinates": [coords]})
    return json.dumps({"type": "LineString", "coordinates": coords})


def places(area_name: str, admin_level: int | None = None):
    for url in OVERPASS:
        try:
            resp = requests.post(url, data={"data": query(area_name, admin_level)}, timeout=180,
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
        yield kind, name, f"{el['type']}/{el['id']}", _geojson(el)


def main(area_name: str, admin_level: int | None = None) -> None:
    repo = EvidenceRepository(load().database_url)
    seen = set()
    for kind, name, osm_id, geojson in places(area_name, admin_level):
        # one row per name: a street drawn as 12 osm ways is still one street
        if (kind, name) in seen:
            continue
        seen.add((kind, name))
        repo.upsert_place(kind, name, name, area_name, osm_id, geojson, "osm")
    print(f"{len(seen)} places from {area_name}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("area", help="osm name of the administrative area")
    ap.add_argument("--admin-level", type=int)
    args = ap.parse_args()
    main(args.area, args.admin_level)
