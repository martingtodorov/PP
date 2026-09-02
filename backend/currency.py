"""Currency helpers.

Prices live in EUR. Storefronts whose country does not use the euro (CZ, HU, PL, RO) are shown and
charged in the local currency, converted with the daily ECB reference rate and rounded up to a
psychological price. Imported Shopify orders can already be in RON/BGN/etc and are normalised to EUR.
"""
import logging
import math
import time
from typing import Any, Dict, Optional
from xml.etree import ElementTree

import httpx

log = logging.getLogger("purepeptide.currency")

# Units of foreign currency per 1 EUR — the fallback when the ECB feed is unreachable
CURRENCY_RATES = {
    "EUR": 1.0,
    "BGN": 1.95583,
    "RON": 4.9750,
    "HUF": 395.0,
    "PLN": 4.30,
    "CZK": 25.20,
    "GBP": 0.845,
    "USD": 1.08,
}

# Storefronts that are charged in their own currency
LOCALE_CURRENCY = {"cz": "CZK", "hu": "HUF", "pl": "PLN", "ro": "RON"}
INTL_LOCALE = {"CZK": "cs-CZ", "HUF": "hu-HU", "PLN": "pl-PL", "RON": "ro-RO", "EUR": "bg-BG"}

ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
_TTL_SECONDS = 6 * 3600
_cache: Dict[str, Any] = {"fetched_at": 0.0, "rates": None, "date": None}


def currency_for_locale(locale: Optional[str]) -> str:
    return LOCALE_CURRENCY.get((locale or "").lower().strip(), "EUR")


def rate_for(currency: str) -> float:
    return CURRENCY_RATES.get((currency or "EUR").upper().strip(), 1.0)


def to_eur(amount, currency: str) -> float:
    try:
        return round(float(amount or 0) / rate_for(currency), 2)
    except (TypeError, ValueError):
        return 0.0


def nice_price(amount_eur, currency: str, rate: float) -> float:
    """EUR -> local, rounded UP to a price that looks like a price (244,73 -> 249 lei).

    The same rule is implemented in the frontend (lib/money.js) — keep them in sync.
    """
    if (currency or "EUR").upper() == "EUR":
        return round(float(amount_eur or 0), 2)
    try:
        raw = float(amount_eur or 0) * float(rate or 0)
    except (TypeError, ValueError):
        return 0.0
    if raw <= 0:
        return 0.0
    if raw < 100:
        return float(math.ceil(raw))
    if raw < 1000:
        return float(math.ceil((raw + 1) / 10) * 10 - 1)
    return float(math.ceil((raw + 10) / 100) * 100 - 10)


async def fetch_ecb_rates() -> Dict[str, Any]:
    """The ECB publishes one reference rate per currency per working day, EUR based."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(ECB_URL)
        r.raise_for_status()
    root = ElementTree.fromstring(r.text)
    ns = {"gesmes": "http://www.gesmes.org/xml/2002-08-01",
          "ecb": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}
    cube = root.find(".//ecb:Cube/ecb:Cube", ns)
    if cube is None:
        raise ValueError("unexpected ECB payload")
    rates = {"EUR": 1.0}
    for child in cube.findall("ecb:Cube", ns):
        cur, value = child.get("currency"), child.get("rate")
        if cur and value:
            rates[cur.upper()] = float(value)
    return {"date": cube.get("time"), "rates": rates}


async def get_rates(db) -> Dict[str, Any]:
    """Memory cache -> stored ECB snapshot -> live ECB -> static fallback."""
    if _cache["rates"] and time.time() - _cache["fetched_at"] < _TTL_SECONDS:
        return {"rates": _cache["rates"], "date": _cache["date"]}

    doc = await db.fx_rates.find_one({"key": "ecb"}, {"_id": 0})
    try:
        fresh = await fetch_ecb_rates()
        if doc is None or doc.get("date") != fresh["date"]:
            await db.fx_rates.update_one(
                {"key": "ecb"},
                {"$set": {"key": "ecb", "date": fresh["date"], "rates": fresh["rates"]}},
                upsert=True,
            )
        doc = fresh
    except Exception as ex:  # network hiccup, ECB downtime, weekend cache miss
        log.warning("ECB rates unavailable (%s) — using the stored snapshot", ex)

    rates = (doc or {}).get("rates") or CURRENCY_RATES
    _cache.update({"fetched_at": time.time(), "rates": rates, "date": (doc or {}).get("date")})
    return {"rates": rates, "date": (doc or {}).get("date")}


async def rate_for_locale(db, locale: Optional[str]) -> Dict[str, Any]:
    currency = currency_for_locale(locale)
    if currency == "EUR":
        return {"currency": "EUR", "rate": 1.0, "date": None, "intl_locale": INTL_LOCALE["EUR"]}
    data = await get_rates(db)
    rate = float(data["rates"].get(currency) or rate_for(currency))
    return {"currency": currency, "rate": rate, "date": data.get("date"),
            "intl_locale": INTL_LOCALE.get(currency, "en-GB")}


def order_amounts(items, totals: Dict[str, float], discount: Dict[str, Any],
                  currency: str, rate: float) -> Dict[str, Any]:
    """Local-currency mirror of an order: unit prices are the rounded ones, totals follow from them."""
    if (currency or "EUR").upper() == "EUR":
        return {"currency": "EUR", "currency_rate": 1.0}
    prices = [nice_price(it["price_eur"], currency, rate) for it in items]
    subtotal = sum(p * it["quantity"] for p, it in zip(prices, items))
    shipping = nice_price(totals.get("shipping_eur") or 0, currency, rate)
    if (discount or {}).get("type") == "percent":
        disc = round(subtotal * float(discount.get("value") or 0) / 100)
    else:
        disc = round(float(totals.get("discount_eur") or 0) * rate)
    return {
        "currency": currency.upper(),
        "currency_rate": round(rate, 6),
        "item_prices": prices,
        "subtotal_orig": round(subtotal, 2),
        "discount_orig": round(min(disc, subtotal), 2),
        "shipping_orig": round(shipping, 2),
        "total_orig": round(max(subtotal - min(disc, subtotal) + shipping, 0), 2),
    }
