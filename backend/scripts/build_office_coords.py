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
    """{normalised locker name: [lat, lng]} from the public BOX NOW location file."""
    r = httpx.get(BOXNOW, timeout=90, headers={"User-Agent": UA})
    r.raise_for_status()
    data = r.json()
    items = data if isinstance(data, list) else (data.get("data") or next(iter(data.values())))
    out = {}
    for a in items:
        try:
            out[norm(a.get("name"))] = [round(float(a["lat"]), 5), round(float(a["lng"]), 5)]
        except (KeyError, TypeError, ValueError):
            continue
    return out


def geocode(query: str) -> list:
    r = httpx.get(NOMINATIM, params={"q": query, "format": "json", "limit": 1},
                  timeout=30, headers={"User-Agent": UA})
    if r.status_code != 200:
        return []
    hits = r.json()
    return [round(float(hits[0]["lat"]), 5), round(float(hits[0]["lon"]), 5)] if hits else []


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
        point = box.get(norm(o.get("name")))
        if point:
            result[f"BG:{o['id']}"] = point
            hits += 1
    print(f"BOX NOW: {hits} lockers matched (of {len(box)} published)")

    if "--geocode" in sys.argv:
        todo = [o for o in snapshot("offices_BG_pigeon_office.json") if f"BG:{o['id']}" not in result]
        print(f"Pigeon: geocoding {len(todo)} offices through Nominatim (1 req/s)…")
        for i, o in enumerate(todo, 1):
            query = f"{o.get('address')}, {o.get('city')}, Bulgaria"
            try:
                point = geocode(query)
            except Exception as exc:
                print(f"  {query}: {exc}")
                point = []
            if point:
                result[f"BG:{o['id']}"] = point
            if i % 25 == 0:
                print(f"  {i}/{len(todo)}")
                OUT.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
            time.sleep(1.1)

    OUT.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    print("wrote", OUT, f"{len(result)} points, {OUT.stat().st_size // 1024} kB")


if __name__ == "__main__":
    main()
