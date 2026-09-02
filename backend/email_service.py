"""Transactional email via Resend.

The API key can come from backend/.env (RESEND_API_KEY) or from the admin
settings document (`resend_api_key`), so the shop owner can rotate keys from
the admin panel without a redeploy.
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

import resend

import email_templates

log = logging.getLogger("purepeptide.email")

BRAND = "#FE6F61"


def _wrap(title: str, body_html: str, footer: str) -> str:
    return f"""<!doctype html><html><body style="margin:0;padding:0;background:#f6f7f9;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f6f7f9;padding:28px 12px;">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border-radius:14px;overflow:hidden;font-family:Helvetica,Arial,sans-serif;">
<tr><td style="background:{BRAND};padding:18px 24px;color:#ffffff;font-size:20px;font-weight:bold;">PurePeptide</td></tr>
<tr><td style="padding:26px 24px 8px;font-size:20px;font-weight:bold;color:#0f172a;">{title}</td></tr>
<tr><td style="padding:0 24px 24px;font-size:14px;line-height:1.65;color:#334155;">{body_html}</td></tr>
<tr><td style="padding:16px 24px;background:#0f172a;color:#94a3b8;font-size:11px;line-height:1.6;">{footer}</td></tr>
</table></td></tr></table></body></html>"""


def _items_table(items: List[Dict[str, Any]]) -> str:
    rows = "".join(
        f'<tr><td style="padding:6px 0;border-bottom:1px solid #eef2f6;">{i["title"]} · {i["variant_name"]} × {i["quantity"]}</td>'
        f'<td align="right" style="padding:6px 0;border-bottom:1px solid #eef2f6;">€{i["price_eur"] * i["quantity"]:.2f}</td></tr>'
        for i in items
    )
    return f'<table role="presentation" width="100%" style="font-size:14px;color:#334155;">{rows}</table>'


async def send_email(to: str, subject: str, html: str, settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    settings = settings or {}
    api_key = (settings.get("resend_api_key") or os.environ.get("RESEND_API_KEY") or "").strip()
    sender = (settings.get("resend_from") or os.environ.get("SENDER_EMAIL") or "onboarding@resend.dev").strip()
    if not api_key:
        log.info("Resend key missing — skipping email to %s", to)
        return {"sent": False, "reason": "no_api_key"}
    resend.api_key = api_key
    params = {"from": sender, "to": [to], "subject": subject, "html": html}
    try:
        res = await asyncio.to_thread(resend.Emails.send, params)
        return {"sent": True, "id": (res or {}).get("id")}
    except Exception as ex:
        log.error("Resend send failed: %s", ex)
        return {"sent": False, "reason": str(ex)}


async def send_order_confirmation(order: Dict[str, Any], bank: Dict[str, Any], settings: Dict[str, Any]):
    locale = order.get("locale") or "bg"
    contact = (settings.get("contact_email") or os.environ.get("CONTACT_EMAIL") or "info@purepeptide.bg").strip()
    subject, html = email_templates.render_order(order, bank, locale, contact)
    return await send_email(order["customer_email"], subject, html, settings)


async def send_abandoned_cart(cart: Dict[str, Any], settings: Dict[str, Any], discount_code: str = "",
                              fx: Optional[Dict[str, Any]] = None):
    locale = cart.get("locale") or "bg"
    contact = (settings.get("contact_email") or os.environ.get("CONTACT_EMAIL") or "info@purepeptide.bg").strip()
    subject, html = email_templates.render_abandoned(cart, locale, contact, discount_code, fx)
    return await send_email(cart["email"], subject, html, settings)


async def send_payment_received(order: Dict[str, Any], settings: Dict[str, Any]):
    body = (
        f"<p>Здравейте, {order['customer_name']},</p>"
        f"<p>Потвърдихме плащането за поръчка <strong>{order['order_number']}</strong>. "
        f"Подготвяме пратката за изпращане.</p>"
    )
    return await send_email(
        order["customer_email"], f"Плащането за {order['order_number']} е потвърдено — PurePeptide",
        _wrap("Плащането е потвърдено", body, "PurePeptide"), settings,
    )


async def send_shipment_created(order: Dict[str, Any], settings: Dict[str, Any]):
    """Waybill issued by NextLevel — courier, number and tracking link, in the customer's language."""
    locale = order.get("locale") or "bg"
    contact = (settings.get("contact_email") or os.environ.get("CONTACT_EMAIL") or "info@purepeptide.bg").strip()
    subject, html = email_templates.render_shipment(order, locale, contact)
    return await send_email(order["customer_email"], subject, html, settings)


async def send_delivered(order: Dict[str, Any], settings: Dict[str, Any]):
    locale = order.get("locale") or "bg"
    contact = (settings.get("contact_email") or os.environ.get("CONTACT_EMAIL") or "info@purepeptide.bg").strip()
    subject, html = email_templates.render_delivered(order, locale, contact)
    return await send_email(order["customer_email"], subject, html, settings)


async def send_shipped(order: Dict[str, Any], tracking: Dict[str, Any], settings: Dict[str, Any]):
    body = (
        f"<p>Здравейте, {order['customer_name']},</p>"
        f"<p>Поръчка <strong>{order['order_number']}</strong> е изпратена с "
        f"{tracking['carrier'].title()}.</p>"
        f"<p>Товарителница: <strong>{tracking['tracking_number']}</strong><br>"
        f"<a href='{tracking['tracking_url']}' style='color:{BRAND}'>Проследи пратката</a></p>"
    )
    return await send_email(
        order["customer_email"], f"Поръчка {order['order_number']} е изпратена — PurePeptide",
        _wrap("Пратката е на път", body, "PurePeptide"), settings,
    )

async def send_order_cancelled(order: Dict[str, Any], settings: Dict[str, Any], reason: str = ""):
    body = (
        f"<p>Здравейте, {order.get('customer_name', '')},</p>"
        f"<p>Поръчка <strong>{order['order_number']}</strong> е отказана и няма да бъде изпратена. "
        f"Нямате какво да плащате.</p>"
        + (f"<p>Причина: {reason}</p>" if reason else "")
        + "<p>Ако това е станало по грешка или искате да поръчате отново, просто ни пишете.</p>"
    )
    return await send_email(
        order["customer_email"], f"Поръчка {order['order_number']} е отказана — PurePeptide",
        _wrap("Поръчката е отказана", body, "PurePeptide"), settings,
    )
