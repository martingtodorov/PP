"""Build data/nextcart/cities_{ISO}.json — the city/postcode index behind the predictive address input.

NextCart's address-suggestions endpoint is unreachable from our servers (the shop is no longer on
Shopify), so the checkout builds its own suggestions from GeoNames (public domain): postal-code
files where they exist, the cities5000 dump for the countries GeoNames has no postal file for
(Greece, Cyprus…).

Run: python backend/scripts/build_city_index.py
"""
import io
import json
import pathlib
import unicodedata
import zipfile

import httpx

DATA = pathlib.Path(__file__).resolve().parents[1] / "data" / "nextcart"
ZIP = "https://download.geonames.org/export/zip/{iso}.zip"
CITIES = "https://download.geonames.org/export/dump/cities5000.zip"
COUNTRIES = ["BG", "RO", "GR", "HU", "PL", "SK", "CZ", "SI", "HR", "IT", "DE", "ES", "FR", "BE",
             "NL", "CY"]


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").strip().lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def place_id(country: str, city: str, post: str) -> int:
    return abs(hash(f"{country}|{norm(city)}|{post}")) % 10_000_000


def rows_from_postal(iso: str) -> list:
    r = httpx.get(ZIP.format(iso=iso), timeout=180, follow_redirects=True)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        raw = z.read(f"{iso}.txt").decode("utf-8")
    out = []
    for line in raw.splitlines():
        f = line.split("\t")
        if len(f) < 11 or not f[2] or not f[9]:
            continue
        city = f[2].split("/")[0].strip()
        out.append({"city": city, "postal_code": f[1].strip(),
                    "lat": round(float(f[9]), 4), "lng": round(float(f[10]), 4)})
    return out


def rows_from_cities(iso: str, dump: str) -> list:
    out = []
    for line in dump.splitlines():
        f = line.split("\t")
        if len(f) < 15 or f[8] != iso:
            continue
        out.append({"city": f[1].strip(), "postal_code": "",
                    "lat": round(float(f[4]), 4), "lng": round(float(f[5]), 4),
                    "pop": int(f[14] or 0)})
    out.sort(key=lambda c: -c.get("pop", 0))
    return out


def main():
    dump = None
    for iso in COUNTRIES:
        try:
            rows = rows_from_postal(iso)
        except Exception:
            if dump is None:
                r = httpx.get(CITIES, timeout=240, follow_redirects=True)
                r.raise_for_status()
                with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                    dump = z.read("cities5000.txt").decode("utf-8")
            rows = rows_from_cities(iso, dump)
            print(f"{iso}: no postal file — {len(rows)} cities from the dump")

        seen, per_city, cities = set(), {}, []
        for row in rows:
            name = norm(row["city"])
            key = (name, row["postal_code"])
            # a big city has dozens of postal codes — a handful is enough for the dropdown
            if key in seen or not row["city"] or per_city.get(name, 0) >= 6:
                continue
            seen.add(key)
            per_city[name] = per_city.get(name, 0) + 1
            cities.append({"city": row["city"], "postal_code": row["postal_code"],
                           "place_id": place_id(iso, row["city"], row["postal_code"]),
                           "lat": row["lat"], "lng": row["lng"]})
        path = DATA / f"cities_{iso}.json"
        path.write_text(json.dumps({"cities": cities}, ensure_ascii=False, separators=(",", ":")))
        print(f"{iso}: {len(cities)} entries, {path.stat().st_size // 1024} kB")


if __name__ == "__main__":
    main()
