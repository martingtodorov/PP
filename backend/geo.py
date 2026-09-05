"""Client geo lookup — used to pre-select the country and the nearest pickup points at checkout.

ipwho.is answers with Latin city names ("Sozopol"), while the courier offices are in Cyrillic
("СОЗОПОЛ"), so the raw IP city never matched anything in Bulgaria. Coordinates are therefore
reverse-geocoded through Nominatim, which returns the local spelling, and the browser can send its
own precise position (/geo/reverse) when the visitor allows it — an IP is often registered in a
completely different town than the person using it.
"""
import logging
import os
import time
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Query, Request

log = logging.getLogger("purepeptide.geo")

router = APIRouter(prefix="/geo", tags=["geo"])
DEFAULT_COUNTRY = os.environ["NEXTCART_COUNTRY"]
NOMINATIM = "https://nominatim.openstreetmap.org/reverse"
PHOTON = "https://photon.komoot.io/reverse"
UA = "purepeptide-store/1.0 (+https://purepeptide.bg)"
_cache: Dict[str, tuple] = {}
_places: Dict[str, tuple] = {}
_ip_places: Dict[str, tuple] = {}
_client = httpx.AsyncClient(timeout=httpx.Timeout(connect=2.0, read=3.5, write=3.0, pool=2.0))


def _client_ip(request: Request) -> Optional[str]:
    fwd = (request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for")
           or request.headers.get("x-real-ip") or "")
    ip = fwd.split(",")[0].strip() or (request.client.host if request.client else "")
    if not ip or ip.startswith(("10.", "192.168.", "127.", "172.16.", "::1")):
        return None
    return ip


async def _nominatim(lat: float, lon: float) -> Dict[str, Any]:
    r = await _client.get(NOMINATIM, headers={"User-Agent": UA, "Accept-Language": "bg,en"},
                          params={"lat": lat, "lon": lon, "format": "json", "zoom": 13,
                                  "accept-language": "bg"})
    addr = (r.json() or {}).get("address") or {}
    city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("municipality")
    if not city:
        return {}
    return {"city": city, "postal_code": addr.get("postcode") or "",
            "country": (addr.get("country_code") or "").upper()}


async def _photon(lat: float, lon: float) -> Dict[str, Any]:
    """Second opinion when Nominatim is down or rate limits us — same OSM data, other host."""
    r = await _client.get(PHOTON, headers={"User-Agent": UA},
                          params={"lat": lat, "lon": lon, "lang": "default", "limit": 1})
    props = ((r.json() or {}).get("features") or [{}])[0].get("properties") or {}
    city = props.get("city") or props.get("county") or props.get("locality")
    if not city:
        return {}
    return {"city": city, "postal_code": props.get("postcode") or "",
            "country": (props.get("countrycode") or "").upper()}


async def _reverse(lat: float, lon: float) -> Dict[str, Any]:
    """Coordinates -> local place name, cached per ~1km square."""
    key = f"{round(float(lat), 2)},{round(float(lon), 2)}"
    hit = _places.get(key)
    if hit and hit[0] > time.time():
        return hit[1]
    out: Dict[str, Any] = {}
    for provider in (_nominatim, _photon):
        try:
            out = await provider(lat, lon)
        except Exception as ex:
            log.info("Reverse geocode via %s failed for %s: %s", provider.__name__, key, ex)
        if out:
            break
    if out:
        _places[key] = (time.time() + 86400, out)
    return out


@router.get("/country")
async def geo_country(request: Request):
    """Best-effort country/city of the visitor; always answers, falls back to the store country."""
    ip = _client_ip(request)
    if not ip:
        return {"country": DEFAULT_COUNTRY, "source": "default"}
    hit = _cache.get(ip)
    if hit and hit[0] > time.time():
        return hit[1]
    result = {"country": DEFAULT_COUNTRY, "source": "default"}
    try:
        r = await _client.get(f"https://ipwho.is/{ip}",
                              params={"fields": "success,country_code,city,latitude,longitude"})
        data = r.json()
        if data.get("success") and data.get("country_code"):
            # Measured: every Bulgarian IP resolves to the country centroid (Sofia), whichever
            # provider is asked — the ISP registration has nothing to do with where the visitor is.
            # So only the country is trusted here; the city comes from the device via /geo/reverse.
            result = {"country": data["country_code"], "city": "", "ip_city": data.get("city") or "",
                      "source": "ip"}
    except Exception as ex:
        log.info("Geo lookup skipped for %s: %s", ip, ex)
    _cache[ip] = (time.time() + 86400, result)
    return result


def client_ip(request: Request) -> Optional[str]:
    """The visitor's IP as seen behind Cloudflare — public helper for the analytics tracker."""
    return _client_ip(request)


async def locate_ip(ip: str) -> Dict[str, str]:
    """{"country": "BG", "city": "Sofia"} from the IP, cached 24h. Empty dict when unknown.

    The city is the ISP registration, so it is an approximation (Shopify's analytics has the same
    limitation) — good enough to see which towns the traffic comes from, not a precise location.
    """
    hit = _ip_places.get(ip)
    if hit and hit[0] > time.time():
        return hit[1]
    out: Dict[str, str] = {}
    try:
        r = await _client.get(f"https://ipwho.is/{ip}",
                              params={"fields": "success,country_code,city"})
        data = r.json()
        if data.get("success") and data.get("country_code"):
            out = {"country": data["country_code"], "city": (data.get("city") or "")[:60]}
    except Exception as ex:
        log.info("Analytics geo lookup skipped for %s: %s", ip, ex)
    if out:
        _ip_places[ip] = (time.time() + 86400, out)
    return out


@router.get("/reverse")
async def geo_reverse(lat: float = Query(...), lon: float = Query(...)):
    """The visitor's own device position — far more accurate than the IP registration.

    The city name is best effort (the reverse geocoder can be rate limited); the coordinates are
    always returned, because they are what ranks the courier offices by distance."""
    place = await _reverse(lat, lon)
    return {"city": "", "postal_code": "", **place, "lat": lat, "lng": lon, "source": "device"}
