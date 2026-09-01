"""Localised, Shopify-style HTML email templates (order confirmation + abandoned cart).

All 11 storefront languages are covered. Rendering is pure string building so the
templates work without any extra dependency.
"""
import os
from typing import Any, Dict, List, Optional

BRAND = "#FE6F61"
DARK = "#0f172a"

LOCALE_ORIGIN = {
    "bg": "https://purepeptide.bg",
    "en": "https://purepeptide.eu/en",
    "fr": "https://purepeptide.eu/fr",
    "de": "https://purepeptide.eu/de",
    "cz": "https://purepeptide.eu/cz",
    "hu": "https://purepeptide.eu/hu",
    "pl": "https://purepeptide.eu/pl",
    "sk": "https://purepeptide.eu/sk",
    "si": "https://purepeptide.eu/si",
    "gr": "https://purepeptide.gr",
    "ro": "https://purepeptide.ro",
}

T: Dict[str, Dict[str, str]] = {
    "bg": {
        "order": "Поръчка", "subject_order": "Поръчка {n} · PurePeptide",
        "title": "Благодарим ви за покупката!", "hello": "Здравейте, {name},",
        "body_ship": "Подготвяме поръчката ви за изпращане. Ще ви известим, когато бъде изпратена.",
        "body_bank": "Ще получите потвърждение по имейл веднага след като плащането постъпи.",
        "summary": "Обобщение на поръчката", "subtotal": "Междинна сума", "discount": "Отстъпка",
        "shipping": "Доставка", "total": "Обща сума", "free": "Безплатно", "saved": "Спестихте",
        "customer_info": "Информация за клиента", "ship_addr": "Адрес за доставка",
        "delivery_method": "Начин на доставка", "payment": "Плащане",
        "cod": "Наложен платеж при получаване", "bank": "Банков превод",
        "bank_details": "Данни за банков превод", "holder": "Получател", "iban": "IBAN",
        "bic": "BIC", "reference": "Основание", "view_order": "Прегледайте поръчката си",
        "or_visit": "или", "visit_shop": "Посетете нашия магазин",
        "footer": "Ако имате въпроси, отговорете на този имейл или ни пишете на",
        "disclaimer": "Продуктите са предназначени единствено за научноизследователски цели.",
        "ab_subject": "Забравихте нещо в количката си 👀", "ab_title": "Вашата количка ви чака",
        "ab_body": "Запазихме артикулите ви. Завършете поръчката си само с няколко клика.",
        "ab_cta": "Завърши поръчката", "qty": "бр.",
    },
    "en": {
        "order": "Order", "subject_order": "Order {n} · PurePeptide",
        "title": "Thank you for your purchase!", "hello": "Hi {name},",
        "body_ship": "We are preparing your order for shipment. We'll let you know once it ships.",
        "body_bank": "You will receive a confirmation email as soon as your payment arrives.",
        "summary": "Order summary", "subtotal": "Subtotal", "discount": "Discount",
        "shipping": "Shipping", "total": "Total", "free": "Free", "saved": "You saved",
        "customer_info": "Customer information", "ship_addr": "Shipping address",
        "delivery_method": "Shipping method", "payment": "Payment",
        "cod": "Cash on delivery", "bank": "Bank transfer",
        "bank_details": "Bank transfer details", "holder": "Beneficiary", "iban": "IBAN",
        "bic": "BIC", "reference": "Reference", "view_order": "View your order",
        "or_visit": "or", "visit_shop": "Visit our store",
        "footer": "If you have any questions, reply to this email or contact us at",
        "disclaimer": "Products are intended for research purposes only.",
        "ab_subject": "You left something in your cart 👀", "ab_title": "Your cart is waiting",
        "ab_body": "We saved your items. Complete your order in just a few clicks.",
        "ab_cta": "Complete my order", "qty": "pcs",
    },
    "fr": {
        "order": "Commande", "subject_order": "Commande {n} · PurePeptide",
        "title": "Merci pour votre achat !", "hello": "Bonjour {name},",
        "body_ship": "Nous préparons votre commande pour l'expédition. Nous vous informerons dès son envoi.",
        "body_bank": "Vous recevrez un e-mail de confirmation dès la réception de votre paiement.",
        "summary": "Récapitulatif de la commande", "subtotal": "Sous-total", "discount": "Remise",
        "shipping": "Livraison", "total": "Total", "free": "Offert", "saved": "Vous avez économisé",
        "customer_info": "Informations client", "ship_addr": "Adresse de livraison",
        "delivery_method": "Mode de livraison", "payment": "Paiement",
        "cod": "Paiement à la livraison", "bank": "Virement bancaire",
        "bank_details": "Coordonnées bancaires", "holder": "Bénéficiaire", "iban": "IBAN",
        "bic": "BIC", "reference": "Référence", "view_order": "Voir votre commande",
        "or_visit": "ou", "visit_shop": "Visitez notre boutique",
        "footer": "Pour toute question, répondez à cet e-mail ou écrivez-nous à",
        "disclaimer": "Produits destinés uniquement à la recherche.",
        "ab_subject": "Vous avez oublié quelque chose dans votre panier 👀",
        "ab_title": "Votre panier vous attend",
        "ab_body": "Nous avons gardé vos articles. Finalisez votre commande en quelques clics.",
        "ab_cta": "Finaliser ma commande", "qty": "pcs",
    },
    "de": {
        "order": "Bestellung", "subject_order": "Bestellung {n} · PurePeptide",
        "title": "Vielen Dank für Ihren Einkauf!", "hello": "Hallo {name},",
        "body_ship": "Wir bereiten Ihre Bestellung für den Versand vor. Wir informieren Sie, sobald sie verschickt wird.",
        "body_bank": "Sie erhalten eine Bestätigung per E-Mail, sobald Ihre Zahlung eingegangen ist.",
        "summary": "Bestellübersicht", "subtotal": "Zwischensumme", "discount": "Rabatt",
        "shipping": "Versand", "total": "Gesamt", "free": "Kostenlos", "saved": "Sie haben gespart",
        "customer_info": "Kundeninformationen", "ship_addr": "Lieferadresse",
        "delivery_method": "Versandart", "payment": "Zahlung",
        "cod": "Nachnahme", "bank": "Banküberweisung",
        "bank_details": "Bankverbindung", "holder": "Empfänger", "iban": "IBAN",
        "bic": "BIC", "reference": "Verwendungszweck", "view_order": "Bestellung ansehen",
        "or_visit": "oder", "visit_shop": "Unseren Shop besuchen",
        "footer": "Bei Fragen antworten Sie einfach auf diese E-Mail oder schreiben Sie an",
        "disclaimer": "Die Produkte sind ausschließlich für Forschungszwecke bestimmt.",
        "ab_subject": "Sie haben etwas im Warenkorb vergessen 👀",
        "ab_title": "Ihr Warenkorb wartet auf Sie",
        "ab_body": "Wir haben Ihre Artikel gespeichert. Schließen Sie Ihre Bestellung mit wenigen Klicks ab.",
        "ab_cta": "Bestellung abschließen", "qty": "Stk.",
    },
    "cz": {
        "order": "Objednávka", "subject_order": "Objednávka {n} · PurePeptide",
        "title": "Děkujeme za váš nákup!", "hello": "Dobrý den, {name},",
        "body_ship": "Připravujeme vaši objednávku k odeslání. Ozveme se, až bude vyexpedována.",
        "body_bank": "Potvrzení vám zašleme e-mailem, jakmile obdržíme vaši platbu.",
        "summary": "Přehled objednávky", "subtotal": "Mezisoučet", "discount": "Sleva",
        "shipping": "Doprava", "total": "Celkem", "free": "Zdarma", "saved": "Ušetřili jste",
        "customer_info": "Informace o zákazníkovi", "ship_addr": "Doručovací adresa",
        "delivery_method": "Způsob dopravy", "payment": "Platba",
        "cod": "Platba na dobírku", "bank": "Bankovní převod",
        "bank_details": "Údaje pro bankovní převod", "holder": "Příjemce", "iban": "IBAN",
        "bic": "BIC", "reference": "Variabilní symbol", "view_order": "Zobrazit objednávku",
        "or_visit": "nebo", "visit_shop": "Navštivte náš obchod",
        "footer": "Máte-li dotazy, odpovězte na tento e-mail nebo nám napište na",
        "disclaimer": "Produkty jsou určeny výhradně pro výzkumné účely.",
        "ab_subject": "Zapomněli jste něco v košíku 👀", "ab_title": "Váš košík na vás čeká",
        "ab_body": "Uložili jsme vaše položky. Dokončete objednávku na několik kliknutí.",
        "ab_cta": "Dokončit objednávku", "qty": "ks",
    },
    "hu": {
        "order": "Megrendelés", "subject_order": "Megrendelés {n} · PurePeptide",
        "title": "Köszönjük a vásárlást!", "hello": "Kedves {name},",
        "body_ship": "Készítjük a csomagját a kiszállításra. Értesítjük, amint elindul.",
        "body_bank": "Visszaigazoló e-mailt küldünk, amint a fizetés beérkezik.",
        "summary": "Megrendelés összegzése", "subtotal": "Részösszeg", "discount": "Kedvezmény",
        "shipping": "Szállítás", "total": "Összesen", "free": "Ingyenes", "saved": "Megtakarítás",
        "customer_info": "Vásárlói adatok", "ship_addr": "Szállítási cím",
        "delivery_method": "Szállítási mód", "payment": "Fizetés",
        "cod": "Utánvét", "bank": "Banki átutalás",
        "bank_details": "Banki átutalás adatai", "holder": "Kedvezményezett", "iban": "IBAN",
        "bic": "BIC", "reference": "Közlemény", "view_order": "Megrendelés megtekintése",
        "or_visit": "vagy", "visit_shop": "Látogasson el az üzletünkbe",
        "footer": "Kérdés esetén válaszoljon erre az e-mailre, vagy írjon nekünk:",
        "disclaimer": "A termékek kizárólag kutatási célra készültek.",
        "ab_subject": "Valamit a kosárban hagyott 👀", "ab_title": "A kosara várja Önt",
        "ab_body": "Elmentettük a termékeit. Fejezze be a rendelést néhány kattintással.",
        "ab_cta": "Rendelés befejezése", "qty": "db",
    },
    "pl": {
        "order": "Zamówienie", "subject_order": "Zamówienie {n} · PurePeptide",
        "title": "Dziękujemy za zakup!", "hello": "Cześć {name},",
        "body_ship": "Przygotowujemy Twoje zamówienie do wysyłki. Powiadomimy Cię, gdy zostanie wysłane.",
        "body_bank": "Potwierdzenie otrzymasz e-mailem zaraz po zaksięgowaniu płatności.",
        "summary": "Podsumowanie zamówienia", "subtotal": "Suma częściowa", "discount": "Rabat",
        "shipping": "Dostawa", "total": "Razem", "free": "Bezpłatnie", "saved": "Zaoszczędziłeś",
        "customer_info": "Dane klienta", "ship_addr": "Adres dostawy",
        "delivery_method": "Sposób dostawy", "payment": "Płatność",
        "cod": "Płatność przy odbiorze", "bank": "Przelew bankowy",
        "bank_details": "Dane do przelewu", "holder": "Odbiorca", "iban": "IBAN",
        "bic": "BIC", "reference": "Tytuł przelewu", "view_order": "Zobacz zamówienie",
        "or_visit": "lub", "visit_shop": "Odwiedź nasz sklep",
        "footer": "W razie pytań odpowiedz na tę wiadomość lub napisz do nas na",
        "disclaimer": "Produkty przeznaczone wyłącznie do celów badawczych.",
        "ab_subject": "Zostawiłeś coś w koszyku 👀", "ab_title": "Twój koszyk czeka",
        "ab_body": "Zachowaliśmy Twoje produkty. Dokończ zamówienie w kilku kliknięciach.",
        "ab_cta": "Dokończ zamówienie", "qty": "szt.",
    },
    "sk": {
        "order": "Objednávka", "subject_order": "Objednávka {n} · PurePeptide",
        "title": "Ďakujeme za váš nákup!", "hello": "Dobrý deň, {name},",
        "body_ship": "Pripravujeme vašu objednávku na odoslanie. Ozveme sa, keď bude expedovaná.",
        "body_bank": "Potvrdenie vám pošleme e-mailom, len čo dostaneme vašu platbu.",
        "summary": "Prehľad objednávky", "subtotal": "Medzisúčet", "discount": "Zľava",
        "shipping": "Doprava", "total": "Celkom", "free": "Zdarma", "saved": "Ušetrili ste",
        "customer_info": "Informácie o zákazníkovi", "ship_addr": "Doručovacia adresa",
        "delivery_method": "Spôsob dopravy", "payment": "Platba",
        "cod": "Platba na dobierku", "bank": "Bankový prevod",
        "bank_details": "Údaje na bankový prevod", "holder": "Príjemca", "iban": "IBAN",
        "bic": "BIC", "reference": "Poznámka pre príjemcu", "view_order": "Zobraziť objednávku",
        "or_visit": "alebo", "visit_shop": "Navštívte náš obchod",
        "footer": "Ak máte otázky, odpovedzte na tento e-mail alebo nám napíšte na",
        "disclaimer": "Produkty sú určené výhradne na výskumné účely.",
        "ab_subject": "Zabudli ste niečo v košíku 👀", "ab_title": "Váš košík na vás čaká",
        "ab_body": "Uložili sme vaše položky. Dokončite objednávku na niekoľko klikov.",
        "ab_cta": "Dokončiť objednávku", "qty": "ks",
    },
    "si": {
        "order": "Naročilo", "subject_order": "Naročilo {n} · PurePeptide",
        "title": "Hvala za vaš nakup!", "hello": "Zdravo, {name},",
        "body_ship": "Vaše naročilo pripravljamo za odpremo. Obvestili vas bomo, ko bo poslano.",
        "body_bank": "Potrditev boste prejeli po e-pošti takoj, ko prispe vaše plačilo.",
        "summary": "Povzetek naročila", "subtotal": "Vmesni znesek", "discount": "Popust",
        "shipping": "Dostava", "total": "Skupaj", "free": "Brezplačno", "saved": "Prihranili ste",
        "customer_info": "Podatki o stranki", "ship_addr": "Naslov za dostavo",
        "delivery_method": "Način dostave", "payment": "Plačilo",
        "cod": "Plačilo po povzetju", "bank": "Bančno nakazilo",
        "bank_details": "Podatki za nakazilo", "holder": "Prejemnik", "iban": "IBAN",
        "bic": "BIC", "reference": "Sklic", "view_order": "Ogled naročila",
        "or_visit": "ali", "visit_shop": "Obiščite našo trgovino",
        "footer": "Če imate vprašanja, odgovorite na to sporočilo ali nam pišite na",
        "disclaimer": "Izdelki so namenjeni izključno raziskovalnim namenom.",
        "ab_subject": "V košarici ste nekaj pozabili 👀", "ab_title": "Vaša košarica vas čaka",
        "ab_body": "Shranili smo vaše izdelke. Zaključite naročilo z nekaj kliki.",
        "ab_cta": "Zaključi naročilo", "qty": "kos",
    },
    "gr": {
        "order": "Παραγγελία", "subject_order": "Παραγγελία {n} · PurePeptide",
        "title": "Σας ευχαριστούμε για την αγορά σας!", "hello": "Γεια σας, {name},",
        "body_ship": "Ετοιμάζουμε την παραγγελία σας για αποστολή. Θα σας ενημερώσουμε μόλις σταλεί.",
        "body_bank": "Θα λάβετε email επιβεβαίωσης μόλις εισπραχθεί η πληρωμή σας.",
        "summary": "Σύνοψη παραγγελίας", "subtotal": "Υποσύνολο", "discount": "Έκπτωση",
        "shipping": "Αποστολή", "total": "Σύνολο", "free": "Δωρεάν", "saved": "Κερδίσατε",
        "customer_info": "Στοιχεία πελάτη", "ship_addr": "Διεύθυνση αποστολής",
        "delivery_method": "Τρόπος αποστολής", "payment": "Πληρωμή",
        "cod": "Αντικαταβολή", "bank": "Τραπεζική μεταφορά",
        "bank_details": "Στοιχεία τραπεζικής μεταφοράς", "holder": "Δικαιούχος", "iban": "IBAN",
        "bic": "BIC", "reference": "Αιτιολογία", "view_order": "Δείτε την παραγγελία σας",
        "or_visit": "ή", "visit_shop": "Επισκεφθείτε το κατάστημά μας",
        "footer": "Για οποιαδήποτε ερώτηση, απαντήστε σε αυτό το email ή γράψτε μας στο",
        "disclaimer": "Τα προϊόντα προορίζονται αποκλειστικά για ερευνητικούς σκοπούς.",
        "ab_subject": "Ξεχάσατε κάτι στο καλάθι σας 👀", "ab_title": "Το καλάθι σας σας περιμένει",
        "ab_body": "Κρατήσαμε τα προϊόντα σας. Ολοκληρώστε την παραγγελία με λίγα κλικ.",
        "ab_cta": "Ολοκλήρωση παραγγελίας", "qty": "τεμ.",
    },
    "ro": {
        "order": "Comandă", "subject_order": "Comanda {n} · PurePeptide",
        "title": "Vă mulțumim pentru achiziție!", "hello": "Bună, {name},",
        "body_ship": "Pregătim comanda pentru expediere. Vă anunțăm imediat ce este trimisă.",
        "body_bank": "Veți primi un e-mail de confirmare imediat ce plata este înregistrată.",
        "summary": "Sumarul comenzii", "subtotal": "Subtotal", "discount": "Reducere",
        "shipping": "Livrare", "total": "Total", "free": "Gratuit", "saved": "Ați economisit",
        "customer_info": "Informații client", "ship_addr": "Adresă de livrare",
        "delivery_method": "Metodă de livrare", "payment": "Plată",
        "cod": "Plată ramburs la livrare", "bank": "Transfer bancar",
        "bank_details": "Detalii transfer bancar", "holder": "Beneficiar", "iban": "IBAN",
        "bic": "BIC", "reference": "Referință", "view_order": "Vezi comanda",
        "or_visit": "sau", "visit_shop": "Vizitați magazinul nostru",
        "footer": "Dacă aveți întrebări, răspundeți la acest e-mail sau scrieți-ne la",
        "disclaimer": "Produsele sunt destinate exclusiv scopurilor de cercetare.",
        "ab_subject": "Ați uitat ceva în coș 👀", "ab_title": "Coșul dvs. vă așteaptă",
        "ab_body": "Am păstrat produsele dvs. Finalizați comanda în doar câteva clicuri.",
        "ab_cta": "Finalizează comanda", "qty": "buc",
    },
}


def tr(locale: str, key: str, **kw) -> str:
    loc = (locale or "bg").lower()
    table = T.get(loc) or T["bg"]
    value = table.get(key) or T["bg"].get(key, key)
    return value.format(**kw) if kw else value


def base_url(locale: str) -> str:
    override = (os.environ.get("PUBLIC_SITE_URL") or "").strip().rstrip("/")
    if override:
        return override
    return LOCALE_ORIGIN.get((locale or "bg").lower(), LOCALE_ORIGIN["bg"])


def _abs(url: str, base: str) -> str:
    if not url:
        return ""
    if url.startswith("http"):
        return url
    return f"{base}{url if url.startswith('/') else '/' + url}"


def _money(v: Any) -> str:
    try:
        return f"€{float(v or 0):.2f}"
    except (TypeError, ValueError):
        return "€0.00"


def _shell(locale: str, order_label: str, title: str, content: str, contact_email: str) -> str:
    base = base_url(locale)
    return f"""<!doctype html>
<html lang="{locale}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title></head>
<body style="margin:0;padding:0;background:#f4f6f8;-webkit-font-smoothing:antialiased;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f8;padding:26px 10px;">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0"
 style="max-width:600px;width:100%;background:#ffffff;border-radius:16px;overflow:hidden;
 font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;
 box-shadow:0 12px 34px rgba(15,23,42,.08);">
  <tr><td style="padding:22px 28px 14px;border-bottom:1px solid #eef2f6;">
    <table role="presentation" width="100%"><tr>
      <td><a href="{base}" style="text-decoration:none;color:{DARK};font-size:19px;font-weight:700;
        letter-spacing:-.3px;"><img src="{base}/logo-header.png" alt="PurePeptide" height="26"
        style="height:26px;display:block;border:0;"></a></td>
      <td align="right" style="color:#94a3b8;font-size:12px;font-weight:600;">{order_label}</td>
    </tr></table>
  </td></tr>
  {content}
  <tr><td style="padding:20px 28px;background:{DARK};color:#94a3b8;font-size:11px;line-height:1.7;">
    {tr(locale, 'footer')} <a href="mailto:{contact_email}" style="color:#cbd5e1;">{contact_email}</a><br>
    {tr(locale, 'disclaimer')}
  </td></tr>
</table></td></tr></table></body></html>"""


def _lines(items: List[Dict[str, Any]], locale: str, base: str) -> str:
    rows = []
    for it in items or []:
        img = _abs(it.get("image") or "", base)
        thumb = (f'<img src="{img}" width="56" height="56" alt="" '
                 f'style="border-radius:10px;border:1px solid #eef2f6;object-fit:cover;">') if img else ""
        price = _money(float(it.get("price_eur") or 0) * int(it.get("quantity") or 1))
        rows.append(
            f'<tr><td width="72" style="padding:12px 0;border-bottom:1px solid #f1f5f9;">{thumb}</td>'
            f'<td style="padding:12px 0;border-bottom:1px solid #f1f5f9;font-size:14px;color:{DARK};">'
            f'<strong>{it.get("title", "")}</strong><br>'
            f'<span style="color:#64748b;font-size:12px;">{it.get("variant_name", "")} · '
            f'{it.get("quantity", 1)} {tr(locale, "qty")}</span></td>'
            f'<td align="right" style="padding:12px 0;border-bottom:1px solid #f1f5f9;font-size:14px;'
            f'color:{DARK};white-space:nowrap;"><strong>{price}</strong></td></tr>'
        )
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{"".join(rows)}</table>'


def _sum_row(label: str, value: str, strong: bool = False) -> str:
    weight = "700" if strong else "400"
    size = "16px" if strong else "14px"
    return (f'<tr><td style="padding:5px 0;font-size:{size};color:#475569;">{label}</td>'
            f'<td align="right" style="padding:5px 0;font-size:{size};color:{DARK};'
            f'font-weight:{weight};white-space:nowrap;">{value}</td></tr>')


def _button(url: str, label: str) -> str:
    return (f'<a href="{url}" style="display:inline-block;background:{BRAND};color:#fff;'
            f'text-decoration:none;font-size:15px;font-weight:600;padding:13px 26px;'
            f'border-radius:999px;">{label}</a>')


def render_order(order: Dict[str, Any], bank: Optional[Dict[str, Any]], locale: str,
                 contact_email: str) -> tuple:
    loc = (locale or order.get("locale") or "bg").lower()
    base = base_url(loc)
    delivery = order.get("delivery") or {}
    ship = order.get("shipping") or {}
    pay_key = order.get("payment_method") or "cod"
    intro = tr(loc, "body_bank") if pay_key == "bank_transfer" else tr(loc, "body_ship")
    order_url = f"{base}/checkout/success/{order.get('id')}"

    summary = [_sum_row(tr(loc, "subtotal"), _money(order.get("subtotal_eur")))]
    if float(order.get("discount_eur") or 0) > 0:
        summary.append(_sum_row(tr(loc, "discount"), f"− {_money(order.get('discount_eur'))}"))
    ship_cost = float(order.get("shipping_eur") or 0)
    summary.append(_sum_row(
        f"{tr(loc, 'shipping')}{' · ' + delivery.get('provider_name') if delivery.get('provider_name') else ''}",
        _money(ship_cost) if ship_cost else tr(loc, "free")))
    summary.append(_sum_row(tr(loc, "total"), _money(order.get("total_eur")), strong=True))

    office = (delivery.get("office") or {})
    addr_html = "<br>".join(x for x in [
        ship.get("full_name") or order.get("customer_name") or "",
        office.get("name") or ship.get("line1") or "",
        f'{ship.get("postal_code", "")} {ship.get("city", "")}'.strip(),
        ship.get("country") or "",
        order.get("customer_phone") or "",
    ] if x)

    bank_block = ""
    if pay_key == "bank_transfer" and bank:
        bank_block = (
            f'<tr><td style="padding:0 28px 22px;">'
            f'<table role="presentation" width="100%" style="background:#f8fafc;border:1px solid #eef2f6;'
            f'border-radius:12px;padding:14px 16px;font-size:13px;color:#334155;">'
            f'<tr><td colspan="2" style="padding-bottom:8px;font-weight:700;color:{DARK};">'
            f'{tr(loc, "bank_details")}</td></tr>'
            f'<tr><td>{bank.get("name", "")}</td><td align="right">{tr(loc, "holder")}: '
            f'<strong>{bank.get("holder", "")}</strong></td></tr>'
            f'<tr><td>{tr(loc, "iban")}: <strong>{bank.get("iban", "")}</strong></td>'
            f'<td align="right">{tr(loc, "bic")}: <strong>{bank.get("bic", "")}</strong></td></tr>'
            f'<tr><td colspan="2" style="padding-top:6px;">{tr(loc, "reference")}: '
            f'<strong>{bank.get("reference") or order.get("order_number", "")}</strong></td></tr>'
            f'</table></td></tr>'
        )

    content = f"""
  <tr><td style="padding:26px 28px 6px;">
    <h1 style="margin:0 0 8px;font-size:24px;line-height:1.25;color:{DARK};">{tr(loc, 'title')}</h1>
    <p style="margin:0 0 6px;font-size:14px;color:#475569;">
      {tr(loc, 'hello', name=(order.get('customer_name') or '').split(' ')[0])}</p>
    <p style="margin:0 0 18px;font-size:14px;color:#475569;line-height:1.7;">{intro}</p>
    {_button(order_url, tr(loc, 'view_order'))}
    <p style="margin:12px 0 0;font-size:12px;color:#94a3b8;">{tr(loc, 'or_visit')}
      <a href="{base}" style="color:{BRAND};">{tr(loc, 'visit_shop')}</a></p>
  </td></tr>
  <tr><td style="padding:22px 28px 0;">
    <h2 style="margin:0 0 4px;font-size:15px;color:{DARK};">{tr(loc, 'summary')}</h2>
    {_lines(order.get('items') or [], loc, base)}
    <table role="presentation" width="100%" style="margin-top:12px;">{''.join(summary)}</table>
  </td></tr>
  {bank_block}
  <tr><td style="padding:18px 28px 26px;border-top:1px solid #eef2f6;">
    <h2 style="margin:0 0 12px;font-size:15px;color:{DARK};">{tr(loc, 'customer_info')}</h2>
    <table role="presentation" width="100%" style="font-size:13px;color:#475569;line-height:1.7;">
      <tr valign="top">
        <td width="50%"><strong style="color:{DARK};">{tr(loc, 'ship_addr')}</strong><br>{addr_html}</td>
        <td width="50%"><strong style="color:{DARK};">{tr(loc, 'payment')}</strong><br>
          {tr(loc, 'bank') if pay_key == 'bank_transfer' else tr(loc, 'cod')}<br><br>
          <strong style="color:{DARK};">{tr(loc, 'delivery_method')}</strong><br>
          {delivery.get('label') or order.get('shipping_method') or ''}
          {('<br>' + office.get('address')) if office.get('address') else ''}
        </td>
      </tr>
    </table>
  </td></tr>"""

    order_label = f"{tr(loc, 'order')} {order.get('order_number', '')}"
    subject = tr(loc, "subject_order", n=order.get("order_number", ""))
    return subject, _shell(loc, order_label, subject, content, contact_email)


def render_abandoned(cart: Dict[str, Any], locale: str, contact_email: str,
                     discount_code: str = "") -> tuple:
    loc = (locale or cart.get("locale") or "bg").lower()
    base = base_url(loc)
    items = cart.get("items") or []
    subtotal = sum(float(i.get("price_eur") or 0) * int(i.get("quantity") or 1) for i in items)
    promo = ""
    if discount_code:
        promo = (f'<p style="margin:14px 0 0;font-size:13px;color:#475569;">'
                 f'<span style="background:#fff1ef;border:1px dashed {BRAND};color:{BRAND};'
                 f'padding:6px 12px;border-radius:8px;font-weight:700;">{discount_code}</span></p>')
    content = f"""
  <tr><td style="padding:26px 28px 6px;">
    <h1 style="margin:0 0 8px;font-size:24px;line-height:1.25;color:{DARK};">{tr(loc, 'ab_title')}</h1>
    <p style="margin:0 0 6px;font-size:14px;color:#475569;">
      {tr(loc, 'hello', name=(cart.get('customer_name') or '').split(' ')[0])}</p>
    <p style="margin:0 0 18px;font-size:14px;color:#475569;line-height:1.7;">{tr(loc, 'ab_body')}</p>
    {_button(f"{base}/cart", tr(loc, 'ab_cta'))}
    {promo}
  </td></tr>
  <tr><td style="padding:22px 28px 26px;">
    {_lines(items, loc, base)}
    <table role="presentation" width="100%" style="margin-top:12px;">
      {_sum_row(tr(loc, 'subtotal'), _money(subtotal), strong=True)}
    </table>
  </td></tr>"""
    subject = tr(loc, "ab_subject")
    return subject, _shell(loc, "", subject, content, contact_email)


# ---------- admin notifications (always Bulgarian) ----------
def _admin_shell(badge: str, title: str, content: str, cta_url: str = "", cta_label: str = "") -> str:
    base = base_url("bg")
    cta = (f'<tr><td style="padding:0 28px 24px;">{_button(cta_url, cta_label)}</td></tr>'
           if cta_url and cta_label else "")
    return f"""<!doctype html>
<html lang="bg"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title></head>
<body style="margin:0;padding:0;background:#0b1220;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0b1220;padding:26px 10px;">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0"
 style="max-width:600px;width:100%;background:#ffffff;border-radius:16px;overflow:hidden;
 font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
  <tr><td style="padding:20px 28px;background:{DARK};">
    <table role="presentation" width="100%"><tr>
      <td><img src="{base}/logo-white.svg" alt="PurePeptide" height="24"
        style="height:24px;display:block;border:0;"></td>
      <td align="right"><span style="background:{BRAND};color:#fff;font-size:11px;font-weight:700;
        letter-spacing:.6px;padding:5px 11px;border-radius:999px;">{badge}</span></td>
    </tr></table>
  </td></tr>
  <tr><td style="padding:24px 28px 4px;">
    <h1 style="margin:0 0 14px;font-size:21px;line-height:1.3;color:{DARK};">{title}</h1>
  </td></tr>
  {content}
  {cta}
  <tr><td style="padding:16px 28px;background:#f8fafc;color:#94a3b8;font-size:11px;line-height:1.6;
    border-top:1px solid #eef2f6;">PurePeptide · автоматично известие от системата</td></tr>
</table></td></tr></table></body></html>"""


def _kv_table(rows: List[tuple]) -> str:
    body = "".join(
        f'<tr><td width="150" style="padding:5px 0;font-size:13px;color:#94a3b8;">{k}</td>'
        f'<td style="padding:5px 0;font-size:13px;color:{DARK};font-weight:600;">{v}</td></tr>'
        for k, v in rows if v
    )
    return f'<table role="presentation" width="100%">{body}</table>'


def render_admin_order(order: Dict[str, Any]) -> tuple:
    base = base_url("bg")
    delivery = order.get("delivery") or {}
    office = delivery.get("office") or {}
    ship = order.get("shipping") or {}
    pay = "Банков превод" if order.get("payment_method") == "bank_transfer" else "Наложен платеж"
    total = _money(order.get("total_eur"))
    rows = [
        ("Клиент", order.get("customer_name") or ""),
        ("Имейл", f'<a href="mailto:{order.get("customer_email", "")}" style="color:{BRAND};">'
                  f'{order.get("customer_email", "")}</a>'),
        ("Телефон", f'<a href="tel:{order.get("customer_phone", "")}" style="color:{BRAND};">'
                    f'{order.get("customer_phone", "")}</a>'),
        ("Плащане", pay),
        ("Доставка", delivery.get("label") or order.get("shipping_method") or ""),
        ("Офис / адрес", office.get("name") or ship.get("line1") or ""),
        ("Град", f'{ship.get("postal_code", "")} {ship.get("city", "")} · {ship.get("country", "")}'.strip()),
        ("Език", (order.get("locale") or "bg").upper()),
    ]
    content = f"""
  <tr><td style="padding:0 28px;">
    <table role="presentation" width="100%" style="background:#f8fafc;border:1px solid #eef2f6;
      border-radius:12px;"><tr>
      <td style="padding:14px 16px;font-size:13px;color:#64748b;">Сума на поръчката</td>
      <td align="right" style="padding:14px 16px;font-size:22px;font-weight:700;color:{DARK};">{total}</td>
    </tr></table>
  </td></tr>
  <tr><td style="padding:18px 28px 0;">{_kv_table(rows)}</td></tr>
  <tr><td style="padding:16px 28px 20px;">
    {_lines(order.get('items') or [], 'bg', base)}
  </td></tr>"""
    subject = f"Нова поръчка {order.get('order_number', '')} · {total}"
    html = _admin_shell("НОВА ПОРЪЧКА", f"Поръчка {order.get('order_number', '')}", content,
                        f"{base}/admin/orders/{order.get('id')}", "Отвори в админ панела")
    return subject, html


def render_admin_contact(msg: Dict[str, Any]) -> tuple:
    base = base_url("bg")
    rows = [
        ("Име", msg.get("name") or ""),
        ("Имейл", f'<a href="mailto:{msg.get("email", "")}" style="color:{BRAND};">{msg.get("email", "")}</a>'),
        ("Телефон", msg.get("phone") or "—"),
        ("Език", (msg.get("locale") or "bg").upper()),
    ]
    content = f"""
  <tr><td style="padding:0 28px;">{_kv_table(rows)}</td></tr>
  <tr><td style="padding:16px 28px 22px;">
    <div style="background:#f8fafc;border:1px solid #eef2f6;border-radius:12px;padding:14px 16px;
      font-size:14px;line-height:1.7;color:#334155;white-space:pre-line;">{msg.get('message', '')}</div>
  </td></tr>"""
    subject = f"Ново запитване от {msg.get('name', '')}"
    html = _admin_shell("ЗАПИТВАНЕ", "Ново запитване от сайта", content,
                        f"{base}/admin/messages", "Отвори съобщенията")
    return subject, html


def render_admin_note(badge: str, title: str, body_html: str, cta_url: str = "",
                      cta_label: str = "") -> str:
    """Simple branded admin notice (test emails, system alerts)."""
    content = (f'<tr><td style="padding:0 28px 22px;font-size:14px;color:#475569;line-height:1.7;">'
               f'{body_html}</td></tr>')
    return _admin_shell(badge, title, content, cta_url, cta_label)
