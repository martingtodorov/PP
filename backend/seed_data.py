"""Entirely fictional fixtures. Never a copy of a merchant's catalog or customer database.

Catalog records are opt-in (ENABLE_DEMO_DATA=true) and only initialize an empty store.
Existing production records and private settings are always the source of truth.
"""
from i18n import SITE_ORIGINS

SEED_VERSION = "fictional-fixtures-v1"
LOCALES = list(SITE_ORIGINS)
BRAND_LOGOS = []

COLLECTIONS = [
    {"handle": "demo-all", "link_key": "catalog", "title": "Измислен тестов каталог",
     "description": "Само измислени примери за проверка на приложението.",
     "image": "/demo-fixture.svg", "sort_order": 0, "menu_order": 0,
     "synthetic_fixture": True,
     "translations": {"en": {"title": "Fictional test catalog", "handle": "demo-all"}}},
    {"handle": "demo-samples", "title": "Измислени примери", "image": "/demo-fixture.svg",
     "sort_order": 1, "menu_order": 1, "synthetic_fixture": True,
     "translations": {"en": {"title": "Fictional samples", "handle": "demo-samples"}}},
]

PRODUCTS = [
    {"handle": f"demo-sample-{name}", "title": f"Измислен пример {name.upper()}",
     "description": "<h2>Тестов пример</h2><p>Изцяло измислен продукт. Не е реална стока и не представлява оферта за продажба.</p>",
     "image": "/demo-fixture.svg", "images": ["/demo-fixture.svg"],
     "variants": [{"name": "Sample", "price_eur": price, "stock": 0, "sku": f"DEMO-{name.upper()}"}],
     "collections": ["demo-all", "demo-samples"], "featured": True, "active": True,
     "synthetic_fixture": True,
     "translations": {"en": {"title": f"Fictional sample {name.upper()}", "handle": f"demo-sample-{name}",
        "description": "<h2>Test fixture</h2><p>An entirely fictional product, not a real item or an offer for sale.</p>"}}}
    for name, price in (("a", 1.23), ("b", 2.34))
]

ARTICLES = [{
    "handle": "demo-article", "title": "Измислен примерен материал",
    "excerpt": "Примерен текст за проверка на изгледа. Не е научна публикация.",
    "body": "<h2>Пример</h2><p>Този измислен текст проверява работата на приложението. Не съдържа реални клиентски или каталожни данни.</p>",
    "image": "/demo-fixture.svg", "published": True, "synthetic_fixture": True,
    "translations": {"en": {"handle": "demo-article", "title": "Fictional example article",
        "excerpt": "Sample layout text, not a scientific publication.",
        "body": "<h2>Example</h2><p>Fictional text for application testing. It contains no real customer or catalog records.</p>"}},
}]

# Application defaults, not a merchant database export. Operational identifiers and bank/contact
# details are intentionally empty and must be configured privately on the running store.
DEFAULT_SETTINGS = {
    "site_name": "PurePeptide", "tagline": "", "hero_title": "PurePeptide",
    "hero_kicker": "", "hero_subtitle": "", "hero_cta_primary": "Каталог",
    "hero_cta_secondary": "", "announcements": [], "announcements_i18n": {},
    "announcement": "", "brand_logos": [], "currency_primary": "EUR",
    "currency_secondary": "BGN", "fx_rate": 1.95583, "footer_text": "",
    "contact_email": "", "contact_phone": "", "seed_version": SEED_VERSION,
    "resend_api_key": "", "resend_from": "", "bank_name": "", "bank_iban": "",
    "bank_bic": "", "bank_holder": "", "company_name": "", "company_eik": "",
    "company_vat": "", "company_address": "", "discount_codes": [],
    # Google Analytics 4: one shop-wide measurement ID, with an optional per-locale/per-domain
    # override ({"bg": "G-…", "en": "G-…"}). Public IDs, so they travel with /api/settings.
    "ga4_measurement_id": "", "ga4_ids": {},
    "locale_routes": {loc: {**route, "home_path": "/", "enabled": True}
                      for loc, route in SITE_ORIGINS.items()},
}