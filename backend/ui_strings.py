"""Admin-editable cart/checkout copy.

The defaults ship with the frontend (i18n/checkoutStrings.js) for all 11 languages; this module only
stores what the shop owner changed, plus the AI translations they asked for, and serves them as an
overlay so a text edit never needs a rebuild.
"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from i18n import LOCALES, LOCALE_META, normalize_locale

log = logging.getLogger("purepeptide.ui_strings")

# Bulgarian source of the cart/checkout copy — mirrors frontend/src/i18n/checkoutStrings.js
# (the storefront runs on a different host, so the bulk translate job needs its own copy;
# tests/test_ui_strings.py guards that the two key sets stay identical).
SOURCE_BG = {
    "cartTitle": "Количка",
    "toCatalog": "Към каталога",
    "summary": "Обобщение",
    "discountLabel": "Отстъпка",
    "shippingLabel": "Доставка",
    "shippingFree": "Безплатна",
    "freeShippingHint": "Добавете още {amount} за безплатна доставка.",
    "totalLabel": "Общо",
    "discountCodePh": "Код за отстъпка",
    "applyBtn": "Приложи",
    "codeApplied": "Код {code} е приложен",
    "termsConsent18": "Аз съм на 18+, купувам за научно-изследователски цели и съм съгласен/а с",
    "termsLinkLabel": "Общите условия",
    "termsRequired": "Моля, приемете общите условия",
    "toPayment": "Към плащане",
    "payHint": "Плащане с банков превод или наложен платеж.",
    "specialInstructions": "Специални инструкции към поръчката",
    "specialInstructionsPh": "Напр. предпочитан офис, час за доставка…",
    "quickOrder": "Бърза поръчка",
    "loadingText": "Зареждане…",
    "yourDetails": "Вашите данни",
    "fullNamePh": "Име и фамилия",
    "emailPh": "Имейл",
    "countryLabel": "Държава",
    "dialLabel": "Код на страната",
    "phonePh": "Телефон",
    "deliverySection": "Доставка",
    "noDelivery": "За тази държава все още не предлагаме доставка.",
    "locateBtn": "Намери най-близките до мен",
    "locatingText": "Търся те…",
    "chooseOffice": "Избери офис",
    "chooseLocker": "Избери автомат",
    "nearestTo": "най-близки до {city}",
    "cityPh": "Град",
    "streetPh": "Улица / квартал",
    "numberPh": "№ / бл. / вх. / ап.",
    "postalPh": "Пощенски код",
    "paymentSection": "Плащане",
    "codLabel": "Наложен платеж при получаване",
    "bankTransferLabel": "Банков превод",
    "bankLabel": "Банка",
    "holderLabel": "Получател",
    "bankRefNote": "Като основание за плащане въведете номера на поръчката, който ще видите веднага след завършване.",
    "yourOrder": "Вашата поръчка",
    "showMoreRefine": "Покажи още — уточни търсенето",
    "destOffice": "до офис",
    "destLocker": "до кутия",
    "destAddress": "до адрес",
    "methodToLocker": "До автомат на {courier}",
    "methodToAddress": "До адрес с {courier}",
    "methodToOffice": "До офис на {courier}",
    "submitOrder": "Завърши поръчката",
    "submittingText": "Изпращане…",
    "orderTitle": "Поръчка",
    "contactSection": "Контакт",
    "namesLabel": "Имена",
    "emailLabel": "Имейл",
    "phoneLabel": "Телефон",
    "haveAccount": "Имате профил?",
    "loginLink": "Влезте",
    "trackOrdersTail": ", за да следите поръчките си.",
    "shippingAddressSection": "Адрес за доставка",
    "addressLabel": "Адрес",
    "cityLabel": "Град",
    "postalLabel": "Пощенски код",
    "notesOptional": "Специални инструкции (по желание)",
    "deliveryMethodSection": "Метод за доставка",
    "changeBtn": "Промени",
    "freeLabel": "Безплатно",
    "paymentMethodSection": "Метод за плащане",
    "bankNoteCheckout": "След потвърждение ще получите банкови данни и референция на поръчката. Поръчката се обработва след получаване на превода.",
    "agreeTermsPre": "Съгласявам се с",
    "termsLower": "общите условия",
    "agreeTermsTail": "и потвърждавам, че поръчвам за научноизследователски цели.",
    "processingText": "Обработка…",
    "thanksTitle": "Благодарим за поръчката!",
    "orderWord": "Поръчка",
    "bankDetailsTitle": "Данни за банков превод",
    "bankDetailsNote": "Преведете точната сума и посочете референция в основанието за плащане.",
    "recipientLabel": "Получател",
    "referenceLabel": "Референция (основание)",
    "amountLabel": "Сума",
    "afterTransferNote": "След получаване на превода ще потвърдим поръчката по имейл и ще я изпратим с избрания куриер. Обработката отнема до 1 работен ден от плащането.",
    "itemsTitle": "Артикули",
    "toHome": "Към началото",
    "myOrders": "Моите поръчки",
    "copiedToast": "Копирано",
    "seoCartTitle": "Кошница",
    "seoCartDesc": "Вашата кошница.",
    "seoCheckoutTitle": "Плащане",
    "seoCheckoutDesc": "Завършване на поръчка.",
    "seoThanksTitle": "Благодарим за поръчката",
    "seoThanksDesc": "Поръчката е получена.",
}


router = APIRouter(tags=["ui-strings"])
SETTINGS_KEY = "ui.strings"

_db = None
_admin_dep = None


async def _admin_guard(request: Request):
    return await _admin_dep(request)


def init(db, admin_dependency) -> APIRouter:
    global _db, _admin_dep
    _db = db
    _admin_dep = admin_dependency
    return router


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _all() -> Dict[str, Dict[str, str]]:
    doc = await _db.settings.find_one({"key": SETTINGS_KEY}, {"_id": 0})
    return ((doc or {}).get("value") or {}).get("strings") or {}


async def _save(strings: Dict[str, Dict[str, str]]) -> None:
    await _db.settings.update_one(
        {"key": SETTINGS_KEY},
        {"$set": {"value": {"strings": strings}, "updated_at": _now()}},
        upsert=True,
    )


@router.get("/ui-strings")
async def get_ui_strings(locale: str = ""):
    """Public overlay — the storefront merges it on top of the bundled defaults."""
    strings = await _all()
    if locale:
        loc = normalize_locale(locale)
        return {"strings": {loc: strings.get(loc, {})}}
    return {"strings": strings}


@router.get("/admin/ui-strings")
async def admin_get_ui_strings(admin=Depends(_admin_guard)):
    doc = await _db.settings.find_one({"key": SETTINGS_KEY}, {"_id": 0})
    return {"strings": ((doc or {}).get("value") or {}).get("strings") or {},
            "updated_at": (doc or {}).get("updated_at") or ""}


@router.put("/admin/ui-strings")
async def admin_save_ui_strings(payload: Dict[str, Any] = Body(...), admin=Depends(_admin_guard)):
    """Save one locale. An empty value drops the override and the bundled default takes over."""
    locale = normalize_locale(payload.get("locale") or "")
    incoming = payload.get("strings") or {}
    if not isinstance(incoming, dict):
        raise HTTPException(400, "Липсват текстове")
    strings = await _all()
    current = dict(strings.get(locale) or {})
    for key, value in incoming.items():
        text = (value or "").strip() if isinstance(value, str) else ""
        if text:
            current[key] = text
        else:
            current.pop(key, None)
    strings[locale] = current
    await _save(strings)
    return {"ok": True, "locale": locale, "count": len(current)}


@router.post("/admin/ui-strings/translate")
async def admin_translate_ui_strings(payload: Dict[str, Any] = Body(...), admin=Depends(_admin_guard)):
    """Translate the Bulgarian source strings into one locale with Claude and store the result."""
    locale = normalize_locale(payload.get("locale") or "")
    source = payload.get("source") or SOURCE_BG
    if locale == "bg":
        raise HTTPException(400, "Българският е изходният език")
    saved = await translate_locale(locale, source)
    return {"ok": True, "locale": locale, "translated": saved}


async def translate_locale(locale: str, source: Dict[str, str] = None) -> Dict[str, str]:
    """Claude-translate the checkout copy into one locale and store it as an override."""
    from anthropic import AsyncAnthropic

    source = source or SOURCE_BG
    api_key = os.environ["ANTHROPIC_API_KEY"]
    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
    language = LOCALE_META[locale]["name"]
    system = (
        "You translate the checkout interface of an e-commerce store. Translate every value from "
        f"Bulgarian into {language}. Keep placeholders like {{amount}}, {{code}}, {{city}} and "
        "{courier} exactly as they are. Keep the strings short — they are buttons, labels and "
        "placeholders in a checkout form. Use the natural commerce wording of the target market. "
        "Return ONLY minified JSON with the same keys, no markdown fences, no commentary."
    )
    client = AsyncAnthropic(api_key=api_key)
    try:
        response = await client.messages.create(
            model=model, max_tokens=8000, system=system,
            messages=[{"role": "user", "content": json.dumps(source, ensure_ascii=False)}],
        )
    finally:
        await client.close()

    block = next((b for b in response.content if getattr(b, "type", None) == "text"), None)
    if block is None:
        raise HTTPException(502, "Claude не върна текст")
    text = block.text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
    try:
        translated = json.loads(text)
    except ValueError:
        raise HTTPException(502, "Отговорът на Claude не е валиден JSON")

    strings = await _all()
    current = dict(strings.get(locale) or {})
    saved = {k: v.strip() for k, v in translated.items()
             if isinstance(v, str) and v.strip() and k in source}
    current.update(saved)
    strings[locale] = current
    await _save(strings)
    return saved


ALL_LOCALES: List[str] = list(LOCALES)
