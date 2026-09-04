"""NextCart / RevOrder pre-checkout proxy.

The live purepeptide.bg Shopify store uses the NextCart (RevOrder) app-embed for its external
pre-checkout. Their storefront API is keyed only by the shop domain, so we proxy it server-side
(fixed shop/country/locale, short-lived caching, graceful degradation) instead of calling it
from the browser.
"""
import functools
import json
import logging
import math
import os
import pathlib
import re
import time
import unicodedata
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query, Request

from currency import to_eur

log = logging.getLogger("purepeptide.nextcart")

BASE = os.environ["NEXTCART_BASE_URL"].rstrip("/")
SHOP = os.environ["NEXTCART_SHOP"]
COUNTRY = os.environ["NEXTCART_COUNTRY"]
LOCALE = os.environ["NEXTCART_LOCALE"]

# Couriers the merchant ships with, per destination country. Everything is cash-on-delivery capable.
COUNTRY_COURIERS: Dict[str, list] = {
    "BG": ["econt", "boxnow", "pigeon"],
    "RO": ["fancourier"],
    "GR": ["speedex"],
    "HU": ["gls"], "PL": ["gls"], "SK": ["gls"], "CZ": ["gls"],
    "SI": ["gls"], "HR": ["gls"], "IT": ["gls"], "DE": ["gls"], "ES": ["gls"],
    "FR": ["gls"], "BE": ["gls"], "NL": ["gls"], "CY": ["gls"],
}

# Prepaid-only markets (owner's decision — no cash on delivery there). Germany keeps COD.
COUNTRY_PAYMENTS: Dict[str, list] = {c: ["bank_transfer"] for c in ("ES", "FR", "BE", "NL", "CY")}

# The merchant's own delivery offer — wins over whatever the NextCart profile says (price and presence).
METHOD_OVERRIDES: Dict[str, Dict[str, Dict[str, Any]]] = {
    "BG": {
        "econt_locker": {"provider_key": "econt", "destination_type": "locker", "price_eur": 3.39},
        "econt_address": {"provider_key": "econt", "destination_type": "address", "price_eur": 4.99},
    },
    "ES": {
        "gls_address": {"provider_key": "gls", "destination_type": "address", "price_eur": 8.99},
    },
    "FR": {
        "gls_address": {"provider_key": "gls", "destination_type": "address", "price_eur": 8.99},
    },
    "BE": {
        "gls_address": {"provider_key": "gls", "destination_type": "address", "price_eur": 8.99},
    },
    "NL": {
        "gls_address": {"provider_key": "gls", "destination_type": "address", "price_eur": 8.99},
    },
    "CY": {
        "gls_address": {"provider_key": "gls", "destination_type": "address", "price_eur": 8.99},
    },
}


def payment_methods_for(country: str) -> list:
    keys = COUNTRY_PAYMENTS.get((country or "").upper())
    return [m for m in PAYMENT_METHODS if not keys or m["key"] in keys]


def cod_allowed(country: str) -> bool:
    return any(m["key"] == "cod" for m in payment_methods_for(country))


def method_price(country: str, method_key: str, destination_type: str = "") -> Optional[float]:
    """Server-side price for a checkout selection (the client must not be able to invent one)."""
    ov = METHOD_OVERRIDES.get(country, {}).get(method_key)
    if ov:
        return float(ov["price_eur"])
    return None


def _apply_overrides(country: str, methods: list, providers: list) -> None:
    for key, ov in METHOD_OVERRIDES.get(country, {}).items():
        pk, dest, price = ov["provider_key"], ov["destination_type"], float(ov["price_eur"])
        existing = next((m for m in methods if m.get("key") == key
                         or (m.get("provider_key") == pk and m.get("destination_type") == dest)), None)
        prov = next((p for p in providers if p.get("key") == pk), None)
        name = (prov or {}).get("name") or (existing or {}).get("provider_name") or pk.title()
        if existing:
            existing.update({"price_amount": price, "currency": "EUR", "price_label": f"€{price:.2f}"})
        else:
            methods.append({
                "key": key, "provider_key": pk, "provider_name": name, "logo_url": (prov or {}).get("logo_url", ""),
                "destination_type": dest, "label": f"To {name} {dest}", "price_amount": price, "currency": "EUR",
                "price_label": f"€{price:.2f}", "can_add_to_summary_total": True,
                "supports_office_selection": dest == "office", "supports_locker_selection": dest == "locker",
                "supports_address": dest == "address", "is_default": False, "is_highlighted": False,
            })
        if prov:
            if dest == "address":
                prov["supports_address"] = True
            else:
                prov["supports_pickup"] = True


# Used when the upstream country profile does not expose the courier we ship with (SI / IT / DE + GLS).
COURIER_FALLBACK: Dict[str, Dict[str, Any]] = {
    "gls": {
        "name": "GLS",
        "logo_url": "https://client.nextcartmanager.com/images/couriers/gls.png?v=3c887c14",
        "destinations": ["office", "address"],
        "price_eur": 8.99,
    },
}

PAYMENT_METHODS = [
    {"key": "cod", "label": "Наложен платеж при получаване", "is_default": True},
    {"key": "bank_transfer", "label": "Банков превод", "is_default": False},
]

router = APIRouter(prefix="/nextcart", tags=["nextcart"])

_client = httpx.AsyncClient(
    base_url=BASE,
    timeout=httpx.Timeout(connect=3.0, read=8.0, write=8.0, pool=3.0),
    limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    headers={"Accept": "application/json", "User-Agent": "purepeptide-store/1.0"},
)
_cache: Dict[str, tuple] = {}

# The production server's IP is rejected by the upstream (HTTP 403), so the checkout falls back to
# the committed snapshot in data/nextcart/ (refresh it with scripts/refresh_nextcart_snapshot.py).
SNAPSHOT_DIR = pathlib.Path(__file__).resolve().parent / "data" / "nextcart"
SNAPSHOT_ONLY = os.environ.get("NEXTCART_SNAPSHOT_ONLY", "").lower() in ("1", "true", "yes")


def _snapshot(name: str) -> Optional[Any]:
    path = SNAPSHOT_DIR / name
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except ValueError:
        log.warning("NextCart snapshot %s is not valid JSON", name)
        return None


def _cached(key: str) -> Optional[Any]:
    hit = _cache.get(key)
    if hit and hit[0] > time.time():
        return hit[1]
    return None


def _store(key: str, ttl: int, value: Any) -> Any:
    _cache[key] = (time.time() + ttl, value)
    return value


async def _get(path: str, params: Dict[str, Any]) -> Any:
    try:
        r = await _client.get(path, params={k: v for k, v in params.items() if v not in (None, "")})
        r.raise_for_status()
        return r.json()
    except (httpx.TimeoutException, httpx.TransportError) as ex:
        log.warning("NextCart unavailable (%s): %s", path, ex)
        raise HTTPException(503, "Услугата за доставки е временно недостъпна")
    except httpx.HTTPStatusError as ex:
        log.warning("NextCart %s -> %s", path, ex.response.status_code)
        raise HTTPException(502, "Услугата за доставки върна грешка")
    except ValueError:
        raise HTTPException(502, "Услугата за доставки върна невалиден отговор")


async def _get_or_snapshot(path: str, params: Dict[str, Any], snapshot: str) -> Any:
    """Upstream first, bundled snapshot when the upstream is blocked / unreachable."""
    if SNAPSHOT_ONLY:
        local = _snapshot(snapshot)
        if local is not None:
            return local
    try:
        return await _get(path, params)
    except HTTPException:
        local = _snapshot(snapshot)
        if local is None:
            raise
        log.warning("NextCart %s unavailable — serving snapshot %s", path, snapshot)
        return local


async def _probe_pickups(country: str, provider_key: str, destination_type: str) -> bool:
    """Does the courier actually have pickup points in that country? (cached, used for fallbacks)"""
    key = f"probe:{country}:{provider_key}:{destination_type}"
    cached = _cached(key)
    if cached is not None:
        return cached
    try:
        data = await _get_or_snapshot(
            "/api/shopify-app/storefront/delivery-offices",
            {"shop": SHOP, "provider_key": provider_key, "destination_type": destination_type,
             "country": country, "limit": 1},
            f"offices_{country}_{provider_key}_{destination_type}.json",
        )
        ok = bool(data.get("offices"))
    except HTTPException:
        ok = False
    return _store(key, 21600, ok)


def _norm_city(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").strip().lower())
    return "".join(c for c in s if not unicodedata.combining(c))


@functools.lru_cache(maxsize=1)
def _office_coords() -> Dict[str, Any]:
    """Exact courier coordinates per office id (scripts/build_office_coords.py)."""
    return _snapshot("office_coords.json") or {}


@functools.lru_cache(maxsize=1)
def _centroids() -> Dict[str, Any]:
    """Postal-code / city coordinates for the pickup points (built by scripts/build_postal_centroids.py)."""
    data = _snapshot("postal_centroids.json")
    return data or {}


def _office_point(country: str, office: Dict[str, Any]) -> Optional[tuple]:
    """(lat, lng, exact) — the courier's own coordinates when we have them, else a centroid."""
    exact = _office_coords().get(f"{country.upper()}:{office.get('id')}")
    if exact:
        return (exact[0], exact[1], True)
    table = _centroids().get(country.upper())
    if not table:
        return None
    code = str(office.get("postal_code") or "").strip()
    point = table.get("post", {}).get(code) or table.get("city", {}).get(_norm_city(office.get("city")))
    return (point[0], point[1], False) if point else None


def sort_by_distance(offices: list, country: str, lat: float, lng: float) -> list:
    """Closest pickup point first — from the courier's own coordinates, else a postal centroid."""
    out = []
    for o in offices:
        point = _office_point(country, o)
        km, exact = None, False
        if point:
            exact = point[2]
            dlat = math.radians(point[0] - lat)
            dlng = math.radians(point[1] - lng)
            a = (math.sin(dlat / 2) ** 2
                 + math.cos(math.radians(lat)) * math.cos(math.radians(point[0])) * math.sin(dlng / 2) ** 2)
            km = round(2 * 6371 * math.asin(min(1.0, math.sqrt(a))), 1)
        out.append({**o, "distance_km": km, "distance_exact": exact})
    out.sort(key=lambda o: (o["distance_km"] is None, o["distance_km"] or 0))
    return out


LOCALE_COUNTRY = {"bg": "BG", "gr": "GR", "ro": "RO", "cz": "CZ", "hu": "HU", "pl": "PL",
                  "sk": "SK", "si": "SI", "de": "DE", "fr": "FR", "en": "DE"}

RETURN_DAYS = 14          # EU right of withdrawal
HANDLING_DAYS = (1, 3)
TRANSIT_DAYS = (1, 3)


async def shipping_summary(locale: str) -> Dict[str, Any]:
    """Delivery + return terms of one storefront, for the product schema (Google merchant listings)."""
    country = LOCALE_COUNTRY.get((locale or "").lower(), "BG")
    price, currency = None, "EUR"
    try:
        cfg = await nextcart_config(country)
        methods = cfg.get("delivery_methods") or []
        currency = cfg.get("storefront_delivery_currency") or "EUR"
        address = [m["price_amount"] for m in methods if m.get("destination_type") == "address"]
        price = min(address) if address else min((m["price_amount"] for m in methods), default=None)
    except Exception as exc:
        log.info("shipping_summary for %s failed: %s", country, exc)
    return {"country": country, "currency": currency, "price": price,
            "handling_days": list(HANDLING_DAYS), "transit_days": list(TRANSIT_DAYS),
            "return_days": RETURN_DAYS}


def _to_eur_method(m: Dict[str, Any]) -> Dict[str, Any]:
    """Storefront totals are in EUR — normalise HUF/PLN/CZK/RON courier prices."""
    cur = (m.get("currency") or "EUR").upper()
    amount = float(m.get("price_amount") or 0)
    eur = round(amount, 2) if cur == "EUR" else to_eur(amount, cur)
    return {**m, "price_amount": eur, "currency": "EUR", "price_label": f"€{eur:.2f}",
            "price_local_amount": amount, "price_local_currency": cur}


async def _shape_delivery(data: Dict[str, Any], country: str) -> Dict[str, Any]:
    """Force the couriers the merchant ships with per country and normalise prices to EUR."""
    allowed = COUNTRY_COURIERS.get(country)
    methods = [_to_eur_method(m) for m in (data.get("delivery_methods") or [])]
    providers = list(data.get("delivery_providers") or [])

    if allowed:
        methods = [m for m in methods if m.get("provider_key") in allowed]
        providers = [p for p in providers if p.get("key") in allowed]
        for pk in allowed:
            fb = COURIER_FALLBACK.get(pk)
            if not fb:
                continue
            have = {m.get("destination_type") for m in methods if m.get("provider_key") == pk}
            price = next((m["price_amount"] for m in methods if m.get("provider_key") == pk),
                         float(fb["price_eur"]))
            missing = [d for d in fb["destinations"] if d not in have
                       and (d == "address" or await _probe_pickups(country, pk, d))]
            if not missing and have:
                continue
            if not have and not missing:
                continue
            dests = sorted(have | set(missing), key=lambda d: fb["destinations"].index(d)
                           if d in fb["destinations"] else 9)
            prov = next((p for p in providers if p.get("key") == pk), None)
            if prov:
                prov["supports_address"] = "address" in dests
                prov["supports_pickup"] = "office" in dests
            else:
                providers.append({"key": pk, "name": fb["name"], "logo_url": fb["logo_url"],
                                  "supports_address": "address" in dests,
                                  "supports_pickup": "office" in dests,
                                  "is_default": False, "is_highlighted": False})
            for d in missing:
                methods.append({
                    "key": f"{pk}_{d}", "provider_key": pk, "provider_name": fb["name"],
                    "logo_url": fb["logo_url"], "destination_type": d,
                    "label": f"To {fb['name']} {d}", "price_amount": price, "currency": "EUR",
                    "price_label": f"€{price:.2f}", "can_add_to_summary_total": True,
                    "supports_office_selection": d == "office", "supports_locker_selection": False,
                    "supports_address": d == "address", "is_default": False, "is_highlighted": False,
                })
        _apply_overrides(country, methods, providers)
        order = {k: i for i, k in enumerate(allowed)}
        dest_order = {"office": 0, "locker": 1, "address": 2}
        providers.sort(key=lambda p: order.get(p.get("key"), 99))
        methods.sort(key=lambda m: (order.get(m.get("provider_key"), 99),
                                    dest_order.get(m.get("destination_type"), 9)))

    for i, m in enumerate(methods):
        m["is_default"] = i == 0

    payments = payment_methods_for(country)
    if payments:
        payments = [{**m, "is_default": i == 0} for i, m in enumerate(payments)]
    out = {**data, "delivery_providers": providers, "delivery_methods": methods,
           "payment_methods": payments, "cod_available": any(m["key"] == "cod" for m in payments),
           "storefront_delivery_country_iso2": country, "storefront_delivery_currency": "EUR"}
    if methods:
        out["delivery_unavailable_reason"] = None
        out["delivery_unavailable_message"] = ""
    else:
        out["delivery_unavailable_message"] = "За тази държава все още не предлагаме доставка."
    return out


COUNTRY_NAME_BG = {
    "BG": "България", "RO": "Румъния", "GR": "Гърция", "HU": "Унгария", "PL": "Полша",
    "SK": "Словакия", "CZ": "Чехия", "SI": "Словения", "HR": "Хърватия", "IT": "Италия",
    "DE": "Германия", "ES": "Испания", "FR": "Франция", "BE": "Белгия", "NL": "Нидерландия",
    "CY": "Кипър",
}

COUNTRY_DIAL = {
    "BG": "359", "RO": "40", "GR": "30", "HU": "36", "PL": "48", "SK": "421", "CZ": "420",
    "SI": "386", "HR": "385", "IT": "39", "DE": "49", "ES": "34", "FR": "33", "BE": "32",
    "NL": "31", "CY": "357",
}


@router.get("/countries")
async def nextcart_countries():
    """Countries we actually ship to — drives the checkout country selector.

    Never fails: the selector (and with it the whole checkout) must render even when neither the
    upstream nor a snapshot is available.
    """
    try:
        cfg = await nextcart_config(COUNTRY)
    except HTTPException:
        log.warning("NextCart config unavailable — countries served from the static list")
        cfg = {}
    terr = {t.get("iso2"): t for t in (cfg.get("precheckout_phone_territories") or [])}
    return {
        "default": COUNTRY,
        "countries": [
            {"iso2": c, "name": COUNTRY_NAME_BG.get(c) or terr.get(c, {}).get("name") or c,
             "dial": terr.get(c, {}).get("dial") or COUNTRY_DIAL.get(c, "")}
            for c in COUNTRY_COURIERS
        ],
    }


@router.get("/config")
async def nextcart_config(country: str = Query("", max_length=2)):
    """Couriers, delivery methods with prices, phone territories, pixel id — per destination country."""
    iso = (country or COUNTRY).upper()
    key = f"config:{iso}:{LOCALE}"
    cached = _cached(key)
    if cached is not None:
        return cached
    data = await _get_or_snapshot(
        "/api/shopify-app/storefront/config",
        {"shop": SHOP, "country": iso, "locale": LOCALE},
        f"config_{iso}.json",
    )
    return _store(key, 600, await _shape_delivery(data, iso))


@router.get("/pickups")
async def nextcart_pickups(
    provider_key: str = Query(..., min_length=2, max_length=40),
    destination_type: str = Query("office", pattern="^(office|locker)$"),
    country: str = Query("", max_length=2),
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lng: Optional[float] = Query(None, ge=-180, le=180),
):
    """Full pickup list (offices / lockers) for the checkout dropdown.

    With the visitor's coordinates the list comes back sorted by distance, closest first."""
    iso = (country or COUNTRY).upper()
    key = f"pickups:{iso}:{provider_key}:{destination_type}"
    cached = _cached(key)
    if cached is None:
        data = await _get_or_snapshot(
            "/api/shopify-app/storefront/delivery-offices",
            {"shop": SHOP, "provider_key": provider_key, "destination_type": destination_type,
             "country": iso, "limit": 3000},
            f"offices_{iso}_{provider_key}_{destination_type}.json",
        )
        offices = [
            {"id": o.get("id") or o.get("code"), "code": o.get("code", ""), "name": o.get("name", ""),
             "city": o.get("city", ""), "address": o.get("address") or o.get("address1") or "",
             "postal_code": o.get("postal_code", "")}
            for o in (data.get("offices") or [])
        ]
        cached = _store(key, 21600, {"pickups": offices, "count": len(offices)})
    if lat is None or lng is None:
        return cached
    return {**cached, "pickups": sort_by_distance(cached["pickups"], iso, lat, lng), "sorted_by": "distance"}


@router.get("/offices")
async def nextcart_offices(
    provider_key: str = Query(..., min_length=2, max_length=40),
    destination_type: str = Query("office", pattern="^(office|locker)$"),
    q: str = Query("", max_length=120),
    limit: int = Query(30, ge=1, le=200),
    country: str = Query("", max_length=2),
):
    iso = (country or COUNTRY).upper()
    key = f"offices:{iso}:{provider_key}:{destination_type}:{q.strip().lower()}:{limit}"
    cached = _cached(key)
    if cached is not None:
        return cached
    if not SNAPSHOT_ONLY:
        try:
            data = await _get(
                "/api/shopify-app/storefront/delivery-offices",
                {"shop": SHOP, "provider_key": provider_key, "destination_type": destination_type,
                 "country": iso, "limit": limit, "q": q.strip()},
            )
            return _store(key, 180, data)
        except HTTPException:
            log.warning("NextCart offices unavailable — serving snapshot for %s/%s", iso, provider_key)
    local = _snapshot(f"offices_{iso}_{provider_key}_{destination_type}.json")
    if local is None:
        raise HTTPException(503, "Услугата за доставки е временно недостъпна")
    needle = q.strip().lower()
    offices = local.get("offices") or []
    if needle:
        offices = [o for o in offices if needle in " ".join(
            str(o.get(f) or "") for f in ("name", "city", "address", "address1", "postal_code")).lower()]
    return _store(key, 180, {**local, "offices": offices[:limit]})


@functools.lru_cache(maxsize=20)
def _city_index(country: str) -> list:
    """Our own city/postcode list per country (scripts/build_city_index.py)."""
    data = _snapshot(f"cities_{country.upper()}.json") or {}
    return data.get("cities") or []


# English names customers type instead of the local one (the index only carries local names).
_EXONYMS = {
    "bucharest": "bucuresti", "prague": "praha", "warsaw": "warszawa", "cracow": "krakow",
    "vienna": "wien", "rome": "roma", "milan": "milano", "munich": "munchen",
    "cologne": "koln", "athens": "athina", "copenhagen": "kobenhavn",
}


def _city_base(name: str) -> str:
    """"Bucureşti 15" and "Bucureşti 77" are postal sectors of one city — show it once."""
    return re.sub(r"\s+\d+$", "", name).strip()


def _city_suggestions(country: str, q: str, limit: int = 8) -> list:
    text = _norm_city(q)
    if len(text) < 2:
        return []
    starts, contains = [], []
    for c in _city_index(country):
        name = _norm_city(c["city"])
        if name.startswith(text):
            starts.append(c)
        elif text in name:
            contains.append(c)
        if len(starts) >= limit * 6:
            break
    if not starts and not contains:
        local = next((v for k, v in _EXONYMS.items() if k.startswith(text)), "")
        if local:
            return _city_suggestions(country, local, limit)
    # more postal codes under the same name = bigger city → show it first
    weight: Dict[str, int] = {}
    for c in starts + contains:
        base = _city_base(c["city"]).lower()
        weight[base] = weight.get(base, 0) + 1

    def rank(c):
        return (-weight[_city_base(c["city"]).lower()], len(c["city"]))

    ranked = sorted(starts, key=rank) + sorted(contains, key=rank)
    out, seen = [], set()
    for c in ranked:
        base = _city_base(c["city"])
        if base.lower() in seen:
            continue
        seen.add(base.lower())
        out.append({"city": base, "postal_code": c["postal_code"], "place_id": c["place_id"]})
        if len(out) >= limit:
            break
    return out


def _city_point(country: str, place_id: Optional[int]) -> Optional[Dict[str, Any]]:
    if not place_id:
        return None
    return next((c for c in _city_index(country) if c["place_id"] == place_id), None)


async def _street_suggestions(country: str, q: str, place_id: Optional[int], limit: int = 8) -> list:
    """Streets come from Photon (OpenStreetMap), biased to the city the customer picked."""
    city = _city_point(country, place_id)
    params: Dict[str, Any] = {"q": f"{q} {city['city']}" if city else q, "limit": limit * 3,
                              "lang": "default"}
    if city:
        params.update({"lat": city["lat"], "lon": city["lng"]})
    r = await _client.get("https://photon.komoot.io/api", params=params,
                          headers={"User-Agent": "purepeptide-store/1.0"})
    typed = _norm_city(q)
    same_city, other = [], []
    seen = set()
    for feat in (r.json() or {}).get("features") or []:
        p = feat.get("properties") or {}
        if (p.get("countrycode") or "").upper() != country.upper():
            continue
        street = p.get("street") or (p.get("name") if p.get("osm_key") == "highway" else "")
        name = _norm_city(street)
        # Photon answers loosely — keep only streets that really contain what the customer typed
        if not street or name in seen or typed not in name:
            continue
        seen.add(name)
        row = {"address1": street, "city": p.get("city") or (city or {}).get("city") or "",
               "postal_code": p.get("postcode") or (city or {}).get("postal_code") or "",
               "place_id": place_id}
        if city and _norm_city(row["city"]) == _norm_city(city["city"]):
            same_city.append(row)
        else:
            other.append(row)
    return (same_city + other)[:limit]


@router.get("/address-suggestions")
async def nextcart_address_suggestions(
    mode: str = Query(..., pattern="^(city|street)$"),
    q: str = Query(..., min_length=2, max_length=120),
    provider_key: str = Query("", max_length=40),
    place_id: Optional[int] = None,
    post: str = Query("", max_length=20),
    country: str = Query("", max_length=2),
):
    """Predictive city / street input for delivery to an address.

    NextCart's own address database is unreachable from our servers, so the suggestions are built
    from our GeoNames city index and OpenStreetMap (Photon) for the streets."""
    iso = (country or COUNTRY).upper()
    if not SNAPSHOT_ONLY:
        try:
            return await _get(
                "/api/shopify-app/storefront/address-suggestions",
                {"shop": SHOP, "mode": mode, "q": q.strip(), "country": iso,
                 "provider_key": provider_key, "place_id": place_id, "post": post, "offset": 0},
            )
        except HTTPException:
            pass
    if mode == "city":
        return {"suggestions": _city_suggestions(iso, q)}
    try:
        return {"suggestions": await _street_suggestions(iso, q.strip(), place_id)}
    except Exception as exc:
        log.info("street suggestions for %s failed: %s", q, exc)
        return {"suggestions": []}


@router.post("/event")
async def nextcart_event(request: Request):
    """Forward pre-checkout analytics to the merchant's NextCart pixel — never blocks checkout."""
    body = await request.json()
    try:
        cfg = await nextcart_config(COUNTRY)
    except HTTPException:
        return {"forwarded": False}
    endpoint = cfg.get("event_endpoint")
    pixel_id = cfg.get("pixel_id")
    if not endpoint or not pixel_id or body.get("event_name") not in (cfg.get("enabled_events") or []):
        return {"forwarded": False}
    try:
        await _client.post(
            endpoint,
            json={"pixel_id": pixel_id, "shop": SHOP, "event_name": body["event_name"],
                  "event_data": body.get("event_data") or {}},
            timeout=4.0,
        )
        return {"forwarded": True}
    except Exception as ex:  # analytics must never break the flow
        log.info("NextCart pixel skipped: %s", ex)
        return {"forwarded": False}
