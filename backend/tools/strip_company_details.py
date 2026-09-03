"""Strip the company identification (name, ЕИК/CUI, registered address) from the legal pages.

    python backend/tools/strip_company_details.py --dry     # show what would change
    python backend/tools/strip_company_details.py           # apply

Runs against whichever MONGO_URL/DB_NAME is in backend/.env, so the same command works on the
production server after a deploy.
"""
import argparse
import asyncio
import os
import re
import sys

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
load_dotenv(os.path.join(ROOT, ".env"))

SLUGS = ["terms-conditions", "terms-of-service", "delivery-and-payment", "shipping-policy",
         "privacy-policy", "refund-policy", "contact-1", "about-us"]
COMPANY_ID = "208640029"

# per locale: (subject form, form after a preposition, prepositions that trigger the second form)
MERCHANT = {
    "bg": ("Търговецът", "Търговеца", ["от", "на", "с", "към", "чрез", "за", "до", "у"]),
    "en": ("the Merchant", "the Merchant", []),
    "ro": ("Comerciantul", "Comerciant", ["de", "către", "de către"]),
    "pl": ("Sprzedawca", "Sprzedawcy", ["od", "przez", "do"]),
    "cz": ("Obchodník", "Obchodníka", ["od", "u"]),
    "sk": ("Obchodník", "Obchodníka", ["od", "u"]),
    "hu": ("A Kereskedő", "a Kereskedő", []),
    "de": ("der Händler", "dem Händler", ["von", "durch", "bei", "mit"]),
    "fr": ("le Vendeur", "le Vendeur", []),
    "si": ("Trgovec", "Trgovca", ["od", "pri"]),
    "gr": ("ο Έμπορος", "τον Έμπορο", ["από", "με", "προς"]),
}
SUFFIX = r"(?:\s*(?:ЕООД|EOOD|OOD|ООД|Ltd\.?|LTD|EOOD\.))"


def clean(html: str, locale: str) -> str:
    if not html:
        return html
    subject, oblique, preps = MERCHANT.get(locale, MERCHANT["en"])

    # 1. the identification clause: "ЕИК 208640029, със седалище и адрес на управление: …"
    html = re.sub(rf",?\s*(?:ЕИК|EIK|CUI|IČO|IČ|NIP|Adószám|ΑΦΜ|VAT|УИК)\s*{COMPANY_ID}[^<]*", "", html)
    html = re.sub(rf",?\s*{COMPANY_ID}[^<]*", "", html)

    # 2. "owned and managed by <b>PurePeptide ЕООД</b>" -> drop the ownership statement entirely
    html = re.sub(r",?\s*(?:собственост и управляван(?:а|о)? от|proprietate și administrat de|"
                  r"owned and operated by|owned and managed by|Eigentum und betrieben von|"
                  r"propriété et exploité par|własność i zarządzany przez|vlastněný a provozovaný|"
                  r"vlastnený a prevádzkovaný|v lasti in upravljan|ιδιοκτησία και διαχείριση|"
                  r"tulajdonában és üzemeltetésében)\s*(?:<b>)?[^<,.]*(?:</b>)?", "", html,
                  flags=re.I)

    # 3. every remaining company mention becomes the generic merchant
    ART_NOM = ["η", "ο", "οι"]
    ART_ACC = ["το", "της", "την", "τη", "τον", "τα", "του"]

    def repl(m):
        prep, tags, close = m.group("prep") or "", m.group("tags") or "", m.group("close") or ""
        bare = prep.strip().lower()
        if locale == "gr" and bare in ART_NOM + ART_ACC:
            # the Greek article belongs to the company name — swap the whole thing
            word = oblique if bare in ART_ACC else subject
            if prep.strip()[:1].isupper():
                word = word[0].upper() + word[1:]
            return f"{tags}{word}{close}"
        word = oblique if bare in preps else subject
        if prep and word[0].isupper() and locale in ("bg", "gr", "de", "fr"):
            word = word[0].lower() + word[1:]
        if not prep:
            word = word[0].upper() + word[1:]
        return f"{prep}{tags}{word}{close}"

    name = (rf"(?P<prep>(?:[^\W\d_]+)\s+)?(?P<tags>(?:<[^>]+>\s*)*)"
            rf"PurePeptide{{suffix}}(?P<close>(?:\s*</(?:b|span|strong)>)*)"
            rf"(?![\w.@-]*\.(?:bg|eu|ro|gr|com))")
    html = re.sub(name.format(suffix=SUFFIX), repl, html)
    html = re.sub(name.format(suffix=r"(?!\s*(?:ЕООД|EOOD|OOD|ООД))"), repl, html)

    # 4. a paragraph that only held the company name is now an orphan line — drop it
    words = "|".join(re.escape(w) for w in {subject, oblique, subject.capitalize()})
    html = re.sub(rf"<(p|h[1-6]|div)[^>]*>\s*(?:<[^>]+>\s*)*(?:{words})[\s.,:;]*(?:</[^>]+>\s*)*</\1>",
                  "", html, flags=re.I)

    # 5. tidy up what the removals left behind
    html = re.sub(r"<b>\s*</b>", "", html)
    html = re.sub(r"\s+,", ",", html)
    html = re.sub(r",\s*,", ",", html)
    html = re.sub(r",\s*(</p>|</li>|\.)", r"\1", html)
    html = re.sub(r"[ \t]{2,}", " ", html)
    return html


def clean_meta(text: str) -> str:
    """SEO title/description keep the brand (that is the shop name) but lose the legal entity."""
    if not text:
        return text
    text = re.sub(rf"(PurePeptide){SUFFIX}", r"\1", text)
    text = re.sub(rf",?\s*(?:ЕИК|EIK|CUI|VAT)\s*{COMPANY_ID}", "", text)
    return re.sub(r"[ \t]{2,}", " ", text)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

    hits = re.compile(rf"PurePeptide{SUFFIX}|{COMPANY_ID}|Бяла река", re.I)
    total = 0
    for page in await db.pages.find({}, {"_id": 0}).to_list(500):
        if page["slug"] not in SLUGS and not hits.search(str(page)):
            continue
        loc = page.get("locale") or "bg"          # pages are stored one document per language
        update, changed = {}, []
        new_html = clean(page.get("html") or "", loc)
        if new_html != (page.get("html") or ""):
            update["html"] = new_html
            changed.append(loc)
        for field in ("seo_title", "seo_description", "title", "menu_title"):
            new_meta = clean_meta(page.get(field) or "")
            if new_meta != (page.get(field) or ""):
                update[field] = new_meta
                changed.append(field)
        translations = page.get("translations") or {}
        for loc, tr in translations.items():
            new = clean(tr.get("html") or "", loc)
            if new != (tr.get("html") or ""):
                translations[loc] = {**tr, "html": new}
                changed.append(loc)
        if changed:
            update["translations"] = translations
            total += 1
            print(f"{page['slug']} [{loc}]")
            if not args.dry:
                await db.pages.update_one({"slug": page["slug"], "locale": page.get("locale")},
                                          {"$set": update})
    print(("Щеше да промени " if args.dry else "Промених ") + f"{total} страници")

    left = []
    for page in await db.pages.find({}, {"_id": 0}).to_list(500):
        if hits.search(str(page)):
            left.append(f"{page['slug']}[{page.get('locale')}]")
    print("остатъци:", left or "няма")


if __name__ == "__main__":
    asyncio.run(main())
