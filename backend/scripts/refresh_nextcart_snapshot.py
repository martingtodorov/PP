"""Refresh the bundled NextCart snapshot used as a fallback when the upstream is unreachable.

pp-back cannot reach api.nextcartmanager.com (the upstream rejects the server), so the storefront
serves the last known-good courier configuration from backend/data/nextcart/ instead of showing an
empty checkout. Run this from a machine that CAN reach the API and commit the result:

    python backend/scripts/refresh_nextcart_snapshot.py
"""
import json
import os
import pathlib
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

BASE = os.environ.get("NEXTCART_BASE_URL", "https://api.nextcartmanager.com").rstrip("/")
SHOP = os.environ.get("NEXTCART_SHOP", "etb7zb-gy.myshopify.com")
LOCALE = os.environ.get("NEXTCART_LOCALE", "bg")
OUT = pathlib.Path(__file__).resolve().parents[1] / "data" / "nextcart"

COUNTRY_COURIERS = {
    "BG": ["econt", "boxnow", "pigeon"],
    "RO": ["fancourier"],
    "GR": ["speedex"],
    "HU": ["gls"], "PL": ["gls"], "SK": ["gls"], "CZ": ["gls"],
    "SI": ["gls"], "HR": ["gls"], "IT": ["gls"], "DE": ["gls"],
}


HEADERS = {"Accept": "application/json", "User-Agent": "purepeptide-store/1.0"}


def fetch(path: str, params: dict):
    url = f"{BASE}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    written = 0
    for country, couriers in COUNTRY_COURIERS.items():
        try:
            cfg = fetch("/api/shopify-app/storefront/config",
                        {"shop": SHOP, "country": country, "locale": LOCALE})
        except Exception as ex:  # noqa: BLE001 — a snapshot refresh must not hide which call failed
            print(f"  config {country}: FAILED {ex}")
            continue
        (OUT / f"config_{country}.json").write_text(json.dumps(cfg, ensure_ascii=False))
        written += 1
        print(f"  config {country}: ok")

        for courier in couriers:
            for dest in ("office", "locker"):
                try:
                    data = fetch("/api/shopify-app/storefront/delivery-offices",
                                 {"shop": SHOP, "provider_key": courier, "destination_type": dest,
                                  "country": country, "limit": 5000})
                except Exception as ex:  # noqa: BLE001
                    print(f"  offices {country}/{courier}/{dest}: skipped ({ex})")
                    continue
                if not data.get("offices"):
                    print(f"  offices {country}/{courier}/{dest}: empty, skipped")
                    continue
                name = f"offices_{country}_{courier}_{dest}.json"
                (OUT / name).write_text(json.dumps(data, ensure_ascii=False))
                written += 1
                print(f"  offices {country}/{courier}/{dest}: {len(data['offices'])} points")

    print(f"{written} snapshot files in {OUT}")
    return 0 if written else 1


if __name__ == "__main__":
    raise SystemExit(main())
