"""NextCart / RevOrder pre-checkout proxy.

The live purepeptide.bg Shopify store uses the NextCart (RevOrder) app-embed for its external
pre-checkout. Their storefront API is keyed only by the shop domain, so we proxy it server-side
(fixed shop/country/locale, short-lived caching, graceful degradation) instead of calling it
from the browser.
"""
import json
import logging
import os
import pathlib
import time
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
    "SI": ["gls"], "HR": ["gls"], "IT": ["gls"], "DE": ["gls"],
}

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
        order = {k: i for i, k in enumerate(allowed)}
        dest_order = {"office": 0, "locker": 1, "address": 2}
        providers.sort(key=lambda p: order.get(p.get("key"), 99))
        methods.sort(key=lambda m: (order.get(m.get("provider_key"), 99),
                                    dest_order.get(m.get("destination_type"), 9)))

    for i, m in enumerate(methods):
        m["is_default"] = i == 0

    out = {**data, "delivery_providers": providers, "delivery_methods": methods,
           "payment_methods": PAYMENT_METHODS, "cod_available": True,
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
    "DE": "Германия",
}


@router.get("/countries")
async def nextcart_countries():
    """Countries we actually ship to — drives the checkout country selector."""
    cfg = await nextcart_config(COUNTRY)
    terr = {t.get("iso2"): t for t in (cfg.get("precheckout_phone_territories") or [])}
    return {
        "default": COUNTRY,
        "countries": [
            {"iso2": c, "name": COUNTRY_NAME_BG.get(c) or terr.get(c, {}).get("name") or c,
             "dial": terr.get(c, {}).get("dial", "")}
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
):
    """Full pickup list (offices / lockers) for the checkout dropdown."""
    iso = (country or COUNTRY).upper()
    key = f"pickups:{iso}:{provider_key}:{destination_type}"
    cached = _cached(key)
    if cached is not None:
        return cached
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
    return _store(key, 21600, {"pickups": offices, "count": len(offices)})


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


@router.get("/address-suggestions")
async def nextcart_address_suggestions(
    mode: str = Query(..., pattern="^(city|street)$"),
    q: str = Query(..., min_length=2, max_length=120),
    provider_key: str = Query("", max_length=40),
    place_id: Optional[int] = None,
    post: str = Query("", max_length=20),
    country: str = Query("", max_length=2),
):
    if SNAPSHOT_ONLY:
        return {"suggestions": []}
    try:
        return await _get(
            "/api/shopify-app/storefront/address-suggestions",
            {"shop": SHOP, "mode": mode, "q": q.strip(), "country": (country or COUNTRY).upper(),
             "provider_key": provider_key, "place_id": place_id, "post": post, "offset": 0},
        )
    except HTTPException:
        # No snapshot possible for a free-text database — the customer types the address manually.
        return {"suggestions": []}


@router.post("/event")
async def nextcart_event(request: Request):
    """Forward pre-checkout analytics to the merchant's NextCart pixel — never blocks checkout."""
    body = await request.json()
    cfg = await nextcart_config(COUNTRY)
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
