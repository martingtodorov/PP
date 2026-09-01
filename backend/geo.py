"""Client geo lookup — used to pre-select the country/dial code at checkout."""
import logging
import os
import time
from typing import Dict, Optional

import httpx
from fastapi import APIRouter, Request

log = logging.getLogger("purepeptide.geo")

router = APIRouter(prefix="/geo", tags=["geo"])
DEFAULT_COUNTRY = os.environ["NEXTCART_COUNTRY"]
_cache: Dict[str, tuple] = {}
_client = httpx.AsyncClient(timeout=httpx.Timeout(connect=2.0, read=3.5, write=3.0, pool=2.0))


def _client_ip(request: Request) -> Optional[str]:
    fwd = request.headers.get("x-forwarded-for") or request.headers.get("x-real-ip") or ""
    ip = fwd.split(",")[0].strip() or (request.client.host if request.client else "")
    if not ip or ip.startswith(("10.", "192.168.", "127.", "172.16.", "::1")):
        return None
    return ip


@router.get("/country")
async def geo_country(request: Request):
    """Best-effort country of the visitor; always answers, falls back to the store country."""
    ip = _client_ip(request)
    if not ip:
        return {"country": DEFAULT_COUNTRY, "source": "default"}
    hit = _cache.get(ip)
    if hit and hit[0] > time.time():
        return hit[1]
    result = {"country": DEFAULT_COUNTRY, "source": "default"}
    try:
        r = await _client.get(f"https://ipwho.is/{ip}", params={"fields": "success,country_code,city,latitude,longitude"})
        data = r.json()
        if data.get("success") and data.get("country_code"):
            result = {"country": data["country_code"], "city": data.get("city") or "",
                      "lat": data.get("latitude"), "lon": data.get("longitude"), "source": "ip"}
    except Exception as ex:
        log.info("Geo lookup skipped for %s: %s", ip, ex)
    _cache[ip] = (time.time() + 86400, result)
    return result
