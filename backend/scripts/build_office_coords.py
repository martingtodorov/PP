"""Build data/nextcart/office_coords.json — exact coordinates per pickup point.

NextCart itself returns no coordinates, so the checkout falls back to postal-code centroids, which
makes every office in a town look equally far away. The couriers that publish their own locations
are fetched here and matched to our office ids:

  * Econt  — official nomenclature API (offices + Econtomats), matched by office code
  * BOX NOW — public location file, matched by locker name
  * Pigeon — no API: geocoded through Nominatim (1 req/s, honours their usage policy)

Everything else keeps the postal-code centroid.

Run: python backend/scripts/build_office_coords.py [--geocode]
"""
import json
import math
import pathlib
import re
import sys
import time
import unicodedata

import httpx

DATA = pathlib.Path(__file__).resolve().parents[1] / "data" / "nextcart"
OUT = DATA / "office_coords.json"
ECONT = "https://ee.econt.com/services/Nomenclatures/NomenclaturesService.getOffices.json"
BOXNOW = "https://locationapi-production.boxnow.bg/v1/apms_bg-BG.json"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
UA = "purepeptide-store/1.0 (office geocoding, contact: info@purepeptide.bg)"


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").strip().lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-zа-я0-9]+", " ", s).strip()


def snapshot(name: str) -> list:
    path = DATA / name
    if not path.is_file():
        return []
    return json.loads(path.read_text()).get("offices") or []


def econt_points() -> dict:
    """{code: [lat, lng]} for every Econt office and Econtomat in Bulgaria."""
    r = httpx.post(ECONT, json={"countryCode": "BGR"}, timeout=90, headers={"Content-Type": "application/json"})
    r.raise_for_status()
    out = {}
    for o in r.json().get("offices") or []:
        loc = (o.get("address") or {}).get("location") or {}
        if loc.get("latitude") and loc.get("longitude"):
            out[str(o.get("code") or "").strip()] = [round(loc["latitude"], 5), round(loc["longitude"], 5)]
            out.setdefault(norm(o.get("name")), out[str(o.get("code") or "").strip()])
    return out


def boxnow_points() -> dict:
    """{normalised locker name / address: [lat, lng]} from the public BOX NOW location file."""
    r = httpx.get(BOXNOW, timeout=90, headers={"User-Agent": UA})
    r.raise_for_status()
    data = r.json()
    items = data if isinstance(data, list) else (data.get("data") or next(iter(data.values())))
    out = {}
    for a in items:
        try:
            point = [round(float(a["lat"]), 5), round(float(a["lng"]), 5)]
        except (KeyError, TypeError, ValueError):
            continue
        out[norm(a.get("name"))] = point
        # a renamed locker is still matched through its address (street + town)
        out.setdefault(f'{norm(a.get("addressLine1"))}|{norm(a.get("addressLine2"))}', point)
    return out


def boxnow_key(office: dict) -> str:
    """Address key of one of our lockers — the street part before the opening-hours note."""
    street = (office.get("address") or "").split("(")[0]
    return f'{norm(street)}|{norm(office.get("city"))}'


PHOTON = "https://photon.komoot.io/api"


def pigeon_query(office: dict) -> str:
    """"Асеновград, 4230, СТОЯН ДЖАНСЪЗОВ, № 1А" → "СТОЯН ДЖАНСЪЗОВ 1А, Асеновград"."""
    parts = [p.strip() for p in (office.get("address") or "").split(",") if p.strip()]
    city = (office.get("city") or "").strip()
    street = [p for p in parts if not p.isdigit() and norm(p) != norm(city)]
    street = " ".join(p.lstrip("№ ").strip() for p in street)
    return f"{street}, {city}, Bulgaria".strip(", ")


def photon(query: str) -> list:
    r = httpx.get(PHOTON, params={"q": query, "limit": 1, "lang": "default"},
                  timeout=30, headers={"User-Agent": UA})
    if r.status_code != 200:
        return []
    for feat in (r.json() or {}).get("features") or []:
        if (feat.get("properties") or {}).get("countrycode", "").upper() != "BG":
            continue
        lng, lat = feat["geometry"]["coordinates"]
        return [round(lat, 5), round(lng, 5)]
    return []


def geocode(query: str) -> list:
    """Photon first (Nominatim rate-limits shared egress IPs hard)."""
    point = photon(query)
    if point:
        return point
    r = httpx.get(NOMINATIM, params={"q": query, "format": "json", "limit": 1},
                  timeout=30, headers={"User-Agent": UA})
    if r.status_code != 200:
        return []
    hits = r.json()
    return [round(float(hits[0]["lat"]), 5), round(float(hits[0]["lon"]), 5)] if hits else []


def centroids() -> dict:
    path = DATA / "postal_centroids.json"
    return json.loads(path.read_text()).get("BG", {}) if path.is_file() else {}


def plausible(point: list, office: dict, table: dict, max_km: float = 20.0) -> bool:
    """A geocoder happily answers with a same-named street in another town — reject those."""
    home = (table.get("post", {}).get(str(office.get("postal_code") or "").strip())
            or table.get("city", {}).get(norm(office.get("city"))))
    if not home or not point:
        return bool(point)
    dlat = math.radians(point[0] - home[0])
    dlng = math.radians(point[1] - home[1])
    a = (math.sin(dlat / 2) ** 2 + math.cos(math.radians(home[0])) * math.cos(math.radians(point[0]))
         * math.sin(dlng / 2) ** 2)
    return 2 * 6371 * math.asin(min(1.0, math.sqrt(a))) <= max_km


def main():
    result = json.loads(OUT.read_text()) if OUT.is_file() else {}

    econt = econt_points()
    matched = 0
    for name in ("offices_BG_econt_office.json", "offices_BG_econt_locker.json"):
        for o in snapshot(name):
            code = str(o.get("code") or "").split("@")[0].strip()
            point = econt.get(code) or econt.get(norm(o.get("name")))
            if point:
                result[f"BG:{o['id']}"] = point
                matched += 1
    print(f"Econt: {matched} offices matched (of {len(econt)} published)")

    box = boxnow_points()
    hits = 0
    for o in snapshot("offices_BG_boxnow_locker.json"):
        point = box.get(norm(o.get("name"))) or box.get(boxnow_key(o))
        if point:
            result[f"BG:{o['id']}"] = point
            hits += 1
    print(f"BOX NOW: {hits} lockers matched (of {len(box)} published)")

    if "--geocode" in sys.argv:
        todo = [o for o in snapshot("offices_BG_pigeon_office.json") if f"BG:{o['id']}" not in result]
        print(f"Pigeon: geocoding {len(todo)} offices (Photon, 1 req/s)…")
        table = centroids()
        found = 0
        for i, o in enumerate(todo, 1):
            query = pigeon_query(o) if o.get("provider_key") == "pigeon" else f"{o.get('address')}, {o.get('city')}, Bulgaria"
            # the house number often has no OSM node — the street itself is still ~50 m accurate
            street_only = re.sub(r"\s*\d+\S*(?=,)", "", query, count=1)
            point = []
            for attempt in [query] + ([street_only] if street_only != query else []):
                try:
                    point = geocode(attempt)
                except Exception as exc:
                    print(f"  {attempt}: {exc}")
                time.sleep(1.1)
                if point and plausible(point, o, table):
                    break
                point = []
            if point:
                result[f"BG:{o['id']}"] = point
                found += 1
            if i % 25 == 0:
                print(f"  {i}/{len(todo)} · {found} located")
                OUT.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")))

    OUT.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    print("wrote", OUT, f"{len(result)} points, {OUT.stat().st_size // 1024} kB")


if __name__ == "__main__":
    main()
