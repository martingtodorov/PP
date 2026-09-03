"""Build data/nextcart/postal_centroids.json — coordinates for every pickup point we ship to.

NextCart does not return coordinates for offices/lockers, so the checkout ranks them by the
centroid of their postal code (GeoNames, public domain), falling back to the city centroid.
Only the postal codes / cities that actually appear in the committed office snapshots are kept,
which keeps the file tiny.

Run: python backend/scripts/build_postal_centroids.py
"""
import io
import json
import pathlib
import unicodedata
import zipfile

import httpx

DATA = pathlib.Path(__file__).resolve().parents[1] / "data" / "nextcart"
OUT = DATA / "postal_centroids.json"
GEONAMES = "https://download.geonames.org/export/zip/{iso}.zip"


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").strip().lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def wanted() -> dict:
    """{country: {"post": {codes...}, "city": {names...}}} from the office snapshots."""
    out: dict = {}
    for path in sorted(DATA.glob("offices_*.json")):
        country = path.stem.split("_")[1].upper()
        try:
            data = json.loads(path.read_text())
        except ValueError:
            continue
        slot = out.setdefault(country, {"post": set(), "city": set()})
        for o in data.get("offices") or []:
            if o.get("postal_code"):
                slot["post"].add(str(o["postal_code"]).strip())
            if o.get("city"):
                slot["city"].add(norm(o["city"]))
    return out


def geonames(iso: str) -> list:
    r = httpx.get(GEONAMES.format(iso=iso), timeout=120, follow_redirects=True)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        raw = z.read(f"{iso}.txt").decode("utf-8")
    rows = []
    for line in raw.splitlines():
        f = line.split("\t")
        if len(f) < 11 or not f[9] or not f[10]:
            continue
        rows.append((f[1].strip(), f[2].strip(), float(f[9]), float(f[10])))
    return rows


CITIES = "https://download.geonames.org/export/dump/cities5000.zip"


def cities_fallback(countries: set) -> dict:
    """Greece (and any country GeoNames has no postal file for) is matched by city name only."""
    r = httpx.get(CITIES, timeout=180, follow_redirects=True)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        raw = z.read("cities5000.txt").decode("utf-8")
    out: dict = {c: {} for c in countries}
    for line in raw.splitlines():
        f = line.split("\t")
        if len(f) < 9 or f[8] not in countries:
            continue
        names = {norm(f[1]), norm(f[2])} | {norm(n) for n in f[3].split(",") if n}
        for name in names:
            out[f[8]].setdefault(name, [round(float(f[4]), 4), round(float(f[5]), 4)])
    return out


def main():
    result = {}
    need_cities = {}
    for country, need in wanted().items():
        try:
            rows = geonames(country)
        except Exception as exc:
            print(f"{country}: no postal file ({type(exc).__name__}) — city names only")
            need_cities[country] = need
            continue
        post, city_acc = {}, {}
        for code, place, lat, lng in rows:
            if code in need["post"] and code not in post:
                post[code] = [round(lat, 4), round(lng, 4)]
            # a Bulgarian office city like "Бургас" is matched by the localised place name too
            for name in {norm(place), norm(place.split("/")[0]), norm(place.split("/")[-1])}:
                if name in need["city"]:
                    acc = city_acc.setdefault(name, [0.0, 0.0, 0])
                    acc[0] += lat
                    acc[1] += lng
                    acc[2] += 1
        city = {k: [round(v[0] / v[2], 4), round(v[1] / v[2], 4)] for k, v in city_acc.items()}
        result[country] = {"post": post, "city": city}
        print(f"{country}: {len(post)}/{len(need['post'])} postal codes, {len(city)}/{len(need['city'])} cities")
    if need_cities:
        all_cities = cities_fallback(set(need_cities))
        for country, need in need_cities.items():
            city = {n: c for n, c in all_cities[country].items() if n in need["city"]}
            result[country] = {"post": {}, "city": city}
            print(f"{country}: {len(city)}/{len(need['city'])} cities (city fallback)")
    OUT.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    print("wrote", OUT, f"{OUT.stat().st_size // 1024} kB")


if __name__ == "__main__":
    main()
