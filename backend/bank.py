"""Bank transfer instructions — editable in the admin panel, env values are the fallback."""
import os
from typing import Any, Dict, Optional

FIELDS = {"name": "BANK_NAME", "iban": "BANK_IBAN", "bic": "BANK_BIC", "holder": "BANK_HOLDER"}


def from_settings(settings: Optional[Dict[str, Any]], reference: str = "",
                  amount_eur: Optional[float] = None) -> Dict[str, Any]:
    settings = settings or {}
    out = {key: (str(settings.get(f"bank_{key}") or "").strip() or os.environ.get(env, ""))
           for key, env in FIELDS.items()}
    out["reference"] = reference
    if amount_eur is not None:
        out["amount_eur"] = amount_eur
    return out


async def details(db, reference: str = "", amount_eur: Optional[float] = None) -> Dict[str, Any]:
    s = await db.settings.find_one({"key": "site"}, {"_id": 0})
    return from_settings((s or {}).get("value"), reference, amount_eur)
