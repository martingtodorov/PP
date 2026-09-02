# PurePeptide — Product Requirements & Status

## Problem statement
Replace the PurePeptide Shopify storefront + admin with a custom stack (React + FastAPI + MongoDB),
mirroring the live shop 1:1 (Bulgarian UI, EUR/BGN dual pricing on .bg), adding a multi-domain /
multi-language storefront, dense internal linking, SEO and a full admin panel.

Domains & languages
- purepeptide.bg → Bulgarian (root, no prefix) — shows EUR + BGN
- purepeptide.eu → **apex unused**, English at `/en`; `/fr /de /cz /hu /pl /sk /si`
- purepeptide.gr → Greek · purepeptide.ro → Romanian
- All locales are also reachable in preview via URL prefixes (`/en`, `/de`, …)
- Locale origins, URL prefixes, homepage paths and enabled flags are editable in **Admin → Езици и URL**

## Design rules (do not break)
- Font: `system-ui` everywhere · Accent: coral `#FE6F61` · Product image backgrounds: pure white
- Mobile header: hamburger + search left, centered logo (`/logo-header.png`), cart right, sliding text nav
- Desktop header: single row — logo left of nav, `Пазарувай` hover mega-menu, search next to cart, no drawer
- Hero is full-bleed on desktop; category tiles small (6-7 across), centred light title, gray overlay
- No customer self-registration; no login icon in the header

## Implemented (June 2026)
- FastAPI + React + MongoDB base, JWT auth in httpOnly cookie, admin seeded
- Catalog mirrored from live Shopify: 7 collections, 16 products (real handles, prices, CDN images), 5 articles
- Locale layer: `translations.{locale}` per product/collection/article (title, subtitle, description,
  handle, menu_title, excerpt, SEO); fallback chain locale → en → bg (bg/en never cross-fallback)
- Per-locale handles: changing a handle for one locale does not affect other domains
- Static localisation: UI strings for 11 locales, English pivot copy for all products/collections/articles,
  per-locale announcement bar messages
- Cart drawer: special instructions, discount codes (WELCOME10 / PEPTIDE20 / SHIP5), terms checkbox gating checkout
- Checkout: bank transfer, discount + note persisted, terms enforced server-side, order confirmation email
- Internal linking: breadcrumbs, sibling collections, related products, related articles, footer link hub,
  cross-domain locale links, hreflang + canonical, JSON-LD (Product / CollectionPage / Article)
- SEO: dynamic `/api/sitemap.xml` (all locales + hreflang alternates), liberal robots.txt (incl. AI crawlers),
  preconnect/preload, skip link, `<main id="main-content">`, image dimensions, a11y descriptions on drawers
- Admin: dashboard, orders, customers, Matrixify import, settings (Resend key/from + test email, discount codes,
  announcements), **product editor** (content per locale, AI translate, image upload to object storage with
  drag & drop / reorder / delete, variants, collections, specs, SEO), **Езици и URL**, **Изтеглени линкове**
  (delisted URL rotation board)
- Emergent object storage for uploads (`POST /api/admin/upload` → `GET /api/files/{path}`)
- Resend transactional email (order confirmation, payment received, shipped) — key configurable in admin

## Latest visual parity round (June 2026)
- Hero = 1:1 port of the owner's Shopify section CSS (`--bg` var, blurred/shifted background, gradient overlay,
  coral primary button, 400px desktop / 360px mobile, tight vertical rhythm)
- Calculator = 1:1 port of the owner's new Shopify calculator (mg / mL / mcg + mL↔Units toggle, coral result bar)
- Product & article cards: portrait 3/4 crop (products) and 1/1 zoom-fill crop (articles), centred titles/prices
- Mobile bestsellers carousel shows 2 cards + a sliver of the third (2.28)
- Category tiles: strong gray overlay, centred small titles, 6-7 across on desktop
- Logo marquee: shadow above and below, minimal padding
- Header: no login icon, no divider between rows; desktop single row with hover mega-menu
- Footer fully localised in all 11 languages (tagline, disclaimer, policy links)
- Fixed: skip-link flash on reload, product image disappearing on hover, `all-peptides` filters now use `base_handle`
  (needed because AI translation generates localised handles)

## Known gaps / blocked
- AI translation now uses the owner's own Anthropic key (`ANTHROPIC_API_KEY`, model `claude-sonnet-5`) —
  single-locale, per-product and background bulk translation of the whole catalog all working.
- Resend is live (`RESEND_API_KEY` in .env). Sender is still `onboarding@resend.dev` — the owner must verify
  purepeptide.bg in Resend and then set the From address in Admin → Настройки.
- Speedy/Econt shipment creation is MOCKED (fake tracking numbers).
- Static page bodies are stored in Mongo (`pages` collection), seeded in bg + en; missing locales fall back
  to English, then Bulgarian.

## 2026-06 — Editable static pages per locale + hero spacing (DONE, tested iteration_8)
- Hero: ~20–24px of air above/below the "PurePeptide" title, ~10px below the CTA row
  (`index.css` last block: `.pp-hero{min-height:0}`, `.pp-hero__inner{padding-block:28px 10px;gap:14px}`).
- New admin section **Страници по език** (`/admin/pages`): 9 slugs × 11 locales, HTML body editor,
  structured FAQ Q&A editor (add / delete / reorder), AI translate from Bulgarian (missing-only or overwrite).
- Backend: `pages_seed.py` (defaults + labels), `seed_pages()` on startup, `ai_translate_page()` in `i18n.py`,
  endpoints `GET /api/pages/{slug}`, `GET/PUT /api/admin/pages[...]`, `POST /api/admin/pages/{slug}/translate`.
- Storefront `StaticPage.jsx` reads from the API with fallback to the previous hardcoded copy.
- Tests: `/app/backend/tests/test_pages.py` (26 cases, all pass).

## 2026-06 (Sept-preview session) — Real data + admin ops
### Matrixify import (real purepeptide.bg data — replaces the demo catalog)
- `/app/backend/matrixify_import.py` reads the Matrixify **.xlsx** export and imports:
  23 products (variants + real SKUs + prices in EUR + stock), 7 collections, 10 static pages (bg),
  19 blog posts, 15 Shopify redirects, 22 discount codes, 1252 customers, 1886 orders (+ spend backfill).
  All Shopify CDN images (products, collections, articles and images inside body HTML) are downloaded into
  Emergent object storage; nothing points at cdn.shopify.com any more. `settings.catalog_imported` blocks re-seeding.
- Admin → **Импорт**: upload any Matrixify .xlsx, tick which sheets to import, optional "don't download images";
  runs as a background job with a live log (`POST /api/admin/import/matrixify`, `GET /api/admin/import/jobs/{id}`).
- Products are all active; each row in Admin → Продукти has an Активен/Скрит toggle
  (`PATCH /api/admin/products/{id}/active`). Hidden products disappear from listings but their page still works.

### Admin analytics (Shopify-style)
- Storefront sends `POST /api/track` on every route change (session id in sessionStorage).
- `GET /api/admin/analytics?range=today|7d|30d|custom` → live visitors (5 min), sessions, sales
  **excluding shipping**, orders, conversion, hourly/daily series + previous-period comparison + deltas.
- Page `/admin/analytics`: dark panel, range pills + custom date range, metric switcher, dashed comparison line.

### Inventory tracking
- `/admin/inventory`: all variants with stock, low/out badges, inline editing, editable low-stock threshold,
  and a movement log. Checkout decrements stock and writes to `inventory_log`.

### Orders (Shopify-app style)
- List `/admin/orders`: search, filters (all / unfulfilled / unpaid / open / archived), rows with total,
  customer • items • time, fulfillment + payment badges, shipping method, pagination.
- Detail `/admin/orders/:id`: fulfillment card (items + "Маркирай като изпратена"), payment card
  (subtotal / shipping / total / paid / balance, "Изпрати фактура по имейл", "Маркирай като платена"),
  customer card where name / email / phone / shipping address are **click-to-copy** (no mailto/tel links).
- Native and Shopify-imported orders are normalised by `_order_view`.
- Order numbers are now random 5-char codes: 3 letters + 2 digits (e.g. `CVY72`).

### Other
- Customers page: imported customers sorted by spend, click a row for the spending history drawer.
- Admin panel is mobile-first: off-canvas sidebar with hamburger + overlay, horizontally scrollable tables.
- Homepage desktop layout matches purepeptide.bg: near full-bleed `.pp-wide` sections, 6 category tiles,
  5.35 product cards visible, 5 articles per row, calculator capped at 860px.
- Hero: ~34px of air above/below the "PurePeptide" title, ~10px under the CTAs.
- Mobile first-tap bug fixed: all hover effects wrapped in `@media (hover: hover) and (pointer: fine)`.
- Product page shows the SKU of the selected variant; admin product list shows all SKUs.
- `/api/files/{path}` now disk-caches images (fast repeat loads).
- Tested: `/app/backend/tests/test_iteration9.py` (35 cases) + iteration_9.json — all pass.

## 2026-06 (Sept-preview session, part 2) — Storefront polish, contact form, push, SEO
- Homepage/desktop: `.pp-wide` near-full-bleed sections, halved vertical paddings, 6 category tiles,
  5.35 product cards, 5 articles per row, calculator ≤860px; article images `scale(1.08) translateY(20px)`.
- Product page: coral package pills (`.pp-variant`, always visible, equal-width, only the active one coral,
  6px radius like the cart button), SKU of the selected variant, coral shadow + hover lift on all coral buttons.
- Product cards: centred coral quick-add (`quick-add-{handle}`) aligned across a row, 0px image→title gap.
- All assets are self-hosted: hero → `/hero-home.png`, marquee logos → object storage, 0 cdn.shopify.com refs.
- Imported HTML cleaned: duplicate `<h1>` removed / demoted to `<h2>` (22 products, 7 collections, 8 pages, 2 articles).
- Manual merchandising: customer sort dropdown removed; `/admin/collections` reorders products per collection
  (`product_order`), "Подреди по продажби" sorts by units sold (all-peptides drives the homepage bestsellers).
- NAD+ and Bacteriostatic water deactivated (`active: false`).
- Contact form (`ContactForm.jsx` on /pages/contacts) → `POST /api/contact`, stored in `contact_messages`,
  emailed (HTML-escaped) to `CONTACT_EMAIL=contact@purepeptide.bg`, admin inbox at `/admin/messages`.
- Web Push (VAPID, pywebpush): `push_service.py`, `/api/push/*`, admin opt-in card in Настройки,
  `/service-worker.js` + `manifest.json` (standalone, logo192/512) — a push is sent on every new order
  and every contact enquiry, fire-and-forget so checkout never blocks. iOS needs Add to Home Screen.
- SEO: real meta titles/descriptions from the live store for every product / collection / page / article
  (Matrixify metafields + `fetch_live_meta.py` scrape for the gaps), absolute og:image with /logo512.png default,
  and full schema.org via `lib/schema.js`: Product+AggregateOffer, CollectionPage+ItemList, FAQPage,
  BlogPosting (Person author), BreadcrumbList, Organization, WebSite+SearchAction.
- Fixed: blank storefront caused by an f-string SyntaxError in server.py (backend crash on reload).
- Tested: iteration_10.json and iteration_11.json — all pass.

## Backlog
- ~~P0: real Matrixify import~~ **DONE (this session)**
- P1: Speedy API integration with real credentials; admin payment verification workflow
- P1: import Shopify menus into the storefront navigation (not done — current nav already matches the live site)
- P2: split `server.py` into route modules; move analytics aggregation into a Mongo pipeline
- P2: abandoned cart recovery, customer accounts created by admin, reviews

## Key endpoints
- Public: `/api/collections`, `/api/collections/{handle}`, `/api/products`, `/api/products/{handle}`,
  `/api/articles`, `/api/settings`, `/api/locales`, `/api/discount/validate`, `/api/checkout`,
  `/api/sitemap.xml`, `/api/robots.txt`, `/api/files/{path}` — all catalog routes accept `?locale=`
- Admin: `/api/admin/products` (CRUD + `/{id}`), `/api/admin/collections`, `/api/admin/upload`,
  `/api/admin/translate`, `/api/admin/settings`, `/api/admin/delisted-links`, `/api/admin/email/test`,
  `/api/admin/orders`, `/api/admin/import/products`

## Admin access
- URL: `https://<domain>/admin/login` (preview: https://shopify-migrate-3.preview.emergentagent.com/admin/login)
- Email `admin@purepeptide.bg`, password `Admin@PurePeptide2026`
- Sections: Табло, Продукти (+ редактор), Поръчки, Клиенти, Импорт, Езици и URL, Страници по език,
  Изтеглени линкове, Настройки

## 2026-09-01 — Currency fix, articles carousel, live-URL alignment, one-click AI translation
### Fixes
- **RON orders**: imported Shopify orders in non-EUR currencies had the foreign amount inside the
  `*_eur` fields. `currency.py` (rates, RON = 4.9750) + `fix_order_currency.py` migration: originals kept in
  `*_orig` / `price_orig`, `*_eur` converted, `currency_rate` + `currency_normalized` flags, customer spend
  re-computed (46 orders, 1017 customers). `_order_view` now returns `*_display` + `price_display`; admin list and
  order detail show the original currency and the EUR equivalent ("курс 4.975 RON/EUR").
- Desktop category tile titles: 13px/12px → **16px / weight 600**.
- Homepage "Научни статии" is now a **single-row scrollable carousel** (`ArticlesCarousel.jsx`,
  `.article-carousel*` CSS): 5 cards desktop with arrows, ~2.3 cards swipeable on mobile.
- One article without an image (`retatrutid-…-9022-78`) got the RETA image.

### Live-URL alignment (`align_live_urls.py`)
- `all-peptides` → **`2all-the-peptides-1`** (live handle); legacy handle still resolves in the API.
- Page slugs now mirror purepeptide.bg: `contact-1`, `about-1`, `become-a-distributor`,
  `terms-conditions`, `delivery-and-payment`, `какво-са-пептиди` (old slugs 404).
- Missing live collection **`retatrutide-price`** created (live meta title/description, `nav_hidden` so it
  does not add a homepage tile).
- The 15 imported Shopify 301 redirects were **removed** (owner's decision).

### SEO / discovery
- Own **HTML sitemap**: `/pages/html-sitemap` + `-products`, `-collections`, `-blogs`, `-articles`, `-pages`
  (`HtmlSitemapPage.jsx`, `GET /api/link-index`), linked from the footer ("Карта на сайта") and from sitemap.xml.
- `GET /api/agents.md` (live product list with prices) + static `/agents.md`,
  `GET /api/sitemap_agentic_discovery.xml`; robots.txt lists both sitemaps + the agents.md hint.
- `sitemap.xml` now contains every page slug and the html-sitemap pages.

### Translations
- **One button** in Admin → Продукти: "Преведи всичко с AI (всички езици)" → `resource: "everything"`
  translates products, collections, **articles (incl. body)** and **pages**, now also **`seo_title` /
  `seo_description`**, into all 10 non-BG locales. Background job with live progress.
- Translation runs on the owner's own **Anthropic Claude key** (`claude-sonnet-5`) — the Emergent key is
  only used for object storage.
- Fixed truncated-JSON failures: `ai_translate_chunked` (2 locales per call, parallel, single-locale retry),
  `max_tokens` 16000 + `stop_reason` guard.
- New **Admin → „Колекции: текст и SEO"** (`/admin/collections/content`): per-locale title/handle/description/
  SEO editor, `nav_hidden` toggle, per-locale or all-locale AI translate.

### Verified
- iteration_13.json (currency + carousel + category text + schema) — all pass.
- iteration_14.json (URL alignment, link-index, sitemaps, agents.md, admin editor) — backend 22/22;
  the html-sitemap sub-route bug it found was fixed (explicit routes) and re-verified manually.

## 2026-09-01 (session 2) — Per-country couriers, checkout fixes, multilingual emails, 90-day memory
### Delivery / couriers (`backend/nextcart.py`)
- `/api/nextcart/config?country=XX` now forces the couriers the merchant ships with, per country:
  **BG** Econt + BoxNow + Pigeon · **RO** FAN Courier · **GR** Speedex ·
  **HU/PL/SK/CZ/SI/HR/IT/DE** GLS (SI/IT/DE synthesized via `COURIER_FALLBACK`, probing real pickup points;
  CZ + IT have no GLS points upstream → "до адрес" only).
- All courier prices normalised to **EUR** (`_to_eur_method` + `currency.py` rates); local amount kept in
  `price_local_amount` / `price_local_currency`.
- **COD first and default everywhere** (`payment_methods[0] = cod`).
- New `/api/nextcart/countries` — the 11 shippable countries with Bulgarian names + dial codes (default BG).
- `country` param added to `/pickups`, `/offices`, `/address-suggestions`.

### Checkout (`frontend/src/components/PreCheckoutModal.jsx`)
- **BUG FIXED (was blocking every order)**: the payload omitted `shipping.full_name` and `shipping.phone`,
  so FastAPI answered 422 and the customer saw "Field required • Field required".
- First + last name merged into **one required field** (`pc-name`, needs 2 words, `autocomplete="name"` for
  Apple autofill) + `onBlur` state sync.
- **Relevance ranking** (`matchScore`): exact city hits beat name/address hits (typing "София" no longer
  surfaces a village), IP city gets a small boost, `dedupeCity` removes "София — София".
- **Fragmented search**: "София Иван Вазов" in the street field resolves the city first, then the street.
- IP city pre-fills the address form only on an exact match; typing in the city clears the stale `place_id`.
- Sub-labels **до офис / до кутия / до адрес** always visible under each courier logo.
- **90-day memory**: `pp_checkout_v1` in localStorage (contact, courier, method, office, address, payment).
- Abandoned-cart capture: debounced `POST /api/cart/track` once the email is valid.
- `locale` sent with the order.
- `formatErr` maps 422 field errors to Bulgarian ("Моля, попълнете: …").

### Emails (`backend/email_templates.py`, `email_service.py`, `abandoned.py`)
- Shopify-style responsive templates: **order confirmation** + **abandoned cart**, translated into all
  **11 locales** (bg, en, fr, de, cz, hu, pl, sk, si, gr, ro) — logo header, order number, line items with
  images, subtotal/shipping/total, bank block (only for bank transfer), customer info, footer.
- **Admin notifications redesigned**: `render_admin_order` (new order — badge, total, customer, courier,
  office, items, "Отвори в админ панела") and `render_admin_contact` (site enquiry), plus
  `render_admin_note` for the admin test email.
- Abandoned carts: `POST /api/cart/track` (one open record per email), background sweeper every
  `ABANDONED_SWEEP_SEC` sending one reminder after `ABANDONED_DELAY_MIN` (60), `mark_recovered` on checkout,
  admin endpoints `/api/admin/abandoned-carts` (+ `/{id}/send`, `/sweep`) and `/api/admin/emails/test`
  (kind=order|abandoned, any locale).
- `PUBLIC_SITE_URL` in backend/.env drives email links/images (leave empty in production to use the
  per-locale domains).

### Other
- Bank details corrected everywhere: **DSK Bank · BG61STSA93000032400775 · STSABGSF · Purepeptide LTD**.
- Homepage heading "Пептиди, изследвани за:" reduced to `text-lg sm:text-xl`.
- RevOrder: `gen_revorder_keys.py` generated an api_key + secret_key + inbound webhook URL per domain
  (purepeptide.bg / .eu / .ro / .gr) — stored in `settings.integrations.revorder`, disabled until enabled.

### Verified
- iteration_19.json — backend 45/45 pytest, frontend e2e (order placement, 90-day memory, country switch,
  sub-labels, bank details, ranking, fragmented search) 100%.
- Admin email templates rendered + delivered via Resend (checked visually).

### Open / next
- Resend is still on the sandbox sender `onboarding@resend.dev` → only the account owner's address receives
  mail. The owner must verify a domain in Resend and set `SENDER_EMAIL`.
- RevOrder outbound push stays **disabled** until the merchant confirms endpoint + enables the domain.
- P2: abandoned-cart second reminder / discount incentive, Speedy API (if still needed).

## 2026-09-01 (session 2, part 2) — Checkout prefetch, phone prefix, media in storage
- **Checkout warm-up** (`frontend/src/lib/checkoutPrefetch.js`): opening the cart drawer prefetches
  countries, bank details, geo, courier config and the default pickup list (5-minute TTL cache).
  The modal now shows couriers in **~0.4s** instead of firing 5 requests on mount.
  `loadSaved` / `saveCheckout` (90-day memory) moved into the same module.
- **Phone prefix is now an independent dropdown** (`pc-dial`, 245 territories). It follows the shipping
  country until the customer picks a prefix himself (`dialTouched`), then the manual choice wins and is
  remembered for 90 days — a Bulgarian number can ship to Greece.
- **Mobile nav drawer**: „Всички пептиди" added as the first item under „Пазарувай"
  (`drawer-collection-all`, new `allPeptides` key in all 11 locales).
- **All images in our own object storage + automatic WebP/JPEG**:
  `migrate_media_to_storage.py` uploaded the remaining site media (hero, logos, OG image) and re-hosted the
  last external Shopify-CDN image inside the chemical-analysis page; `serve_file` now negotiates on the
  `Accept` header (WebP, JPEG fallback), any `?w=` in {160,300,480,600,900,1200}, `Vary: Accept`,
  immutable cache, PIL work off the event loop. Homepage hero comes from `settings.media.hero`.
  Favicons/manifest icons stay in `public/` (browser-level, fixed paths).
- Verified: iteration_20.json — backend 9/9, frontend 100% (prefetch speed, dial dropdown, drawer item,
  image negotiation, hero from storage, no Shopify CDN left).

## 2026-09-01 (session 2, part 3) — Cookie consent + self-hosted deploy package
### Cookie consent
- `frontend/src/components/CookieConsent.jsx` + `frontend/src/i18n/cookies.js`: Shopify-identical wording
  („Ние ценим вашата поверителност" / „Използваме бисквитки, за да подобрим вашето изживяване…"),
  buttons Персонализиране / Отхвърляне на всички / Приемам всички, preferences panel with 4 categories
  (necessary locked, functional, analytics, marketing). Translated into all 11 locales.
- Stored in `pp_cookie_consent_v1` (localStorage) + `pp_consent` cookie (180 days); emits a `pp:consent`
  window event for future analytics wiring. z-index 58 → below the checkout modal (60); the sticky buy bar
  is hidden while the banner is open (`body.pp-consent-open .pp-buybar { display: none }`).

### Self-hosted deploy (Hetzner, systemd + venv + nginx, no Docker)
- `deploy/README.md`, `deploy/hetzner/README.md`, `deploy/requirements-prod.txt`
  (portable — `emergentintegrations` stripped; guarded by `backend/tests/test_requirements_portable.py`).
- `deploy/hetzner/ansible/`: `ansible.cfg`, `inventory.ini.example`, `group_vars/all.yml.example`,
  playbooks `deploy_nat.yml` (WireGuard NAT gateway), `deploy_backend.yml`, `deploy_frontend.yml`,
  `deploy_nginx.yml`, `site.yml`, templates `backend.env.j2`, `purepeptide-backend.service.j2`,
  `nginx-purepeptide.conf.j2`, `wg0-front.conf.j2`, `wg0-back.conf.j2`.
- Hosts: `pp-front` 2.28.79.24 / 10.0.0.2 (nginx, TLS, static build, NAT gateway) and `pp-back` 10.0.0.3
  (FastAPI :8001, MongoDB localhost, media disk). Domains: purepeptide.bg (canonical), .eu, .ro, .gr,
  purepeptide-labs.com — a single build, `REACT_APP_BACKEND_URL` empty.
- **Media is now local-disk-first**: `MEDIA_ROOT` (preview: `backend/.media`, server:
  `/var/lib/purepeptide/media`). `storage.py` reads the disk, falls back to the managed storage and mirrors
  what it fetches; `export_media_to_disk.py` pulls everything once (79 files, 13.9 MB) — after that the
  shop is fully self-hosted. Boot-critical env vars: `MONGO_URL`, `DB_NAME`, `MEDIA_ROOT`.
- One uvicorn worker only (abandoned-cart sweeper + AI translation jobs run in-process).

### Verified
- iteration_21.json — backend 5/5; frontend 6/7 → the reported buy-bar/banner overlap was fixed and
  re-verified manually (banner open → buy bar hidden; after consent → buy bar returns).
- All Ansible YAML parses and every Jinja template renders against `group_vars/all.yml.example`.

## 2026-09-01 (session 2, part 4) — Brand assets in storage + purepeptide-labs.bg alias
- `frontend/src/lib/media.js`: site media map filled from `/api/settings` (`settings.media`), readable from
  non-React modules. Header/desktop/checkout logo, footer light logo, OG image and the schema.org logo now
  come from our object storage (`/api/files/purepeptide/site/...`, served as WebP/JPEG); local files stay as
  fallbacks. `og:image` is always absolute. Favicons + manifest icons stay in `public/` — browsers request
  them at fixed paths.
- `migrate_media_to_storage.py` now also uploads `favicon-512.png` (site media map = hero, logo,
  logo_light, og, icon).
- **`purepeptide-labs.bg` is the Bulgarian alias**: `PROD_HOST_RE` / `isProdHost()` in `i18n/locales.js`
  (used by `seo.js` and `LocaleContext`) recognises `purepeptide(-labs)?.(bg|eu|ro|gr)`, so canonical and
  hreflang stay on `purepeptide.bg` instead of falling back to preview-style prefixes.
  `revorder.DOMAIN_ALIASES` maps the alias to the `purepeptide.bg` credentials. Deploy `site_domains`
  updated (was purepeptide-labs.com).

## 2026-09-01 — Secret audit before GitHub push
- Full scan of the working tree and git history: **no API keys committed** (no Anthropic, Resend, RevOrder,
  Stripe, SSH keys, `.pem`, no `.env`). `.env*`, `inventory.ini`, `group_vars/all.yml`,
  `memory/test_credentials.md`, `backend/.media/` are gitignored; `test_reports/` added to `.gitignore`.
- **Fixed**: `server.py` had `ADMIN_EMAIL` / `ADMIN_PASSWORD` fallback defaults (the preview admin password
  was therefore in the repo). Both are now `os.environ[...]` — the backend refuses to boot without them,
  same as `JWT_SECRET` / `MONGO_URL` / `DB_NAME` / `MEDIA_ROOT`. Guarded by a new test in
  `backend/tests/test_requirements_portable.py`.
- The dev test suite and old test reports still contain the preview admin password → rotate
  `ADMIN_PASSWORD` before going live.

## 2026-06 — Ansible/Hetzner deployment fixed in the repo (no local patches any more)
### Root cause of the recurring "handshake OK but no internet" outage
systemd-networkd deletes routes and routing-policy rules it does not manage
(`ManageForeignRoutes` / `ManageForeignRoutingPolicyRules` default to `yes`). Any networkd reload
(netplan apply, package install, DHCP renew, cloud-init) wiped `default dev wg0 table 100` + both
`ip rule` entries added by wg-quick PostUp, while wg0 itself kept handshaking → `ping 1.1.1.1`
"Network is unreachable" and DNS failures (1.1.1.1/8.8.8.8 are only reachable through wg0).
That is also why `bootstrap_backend_base.yml` died on the MongoDB apt key.

### Repo-level fixes (all committed)
- `ansible/tasks/wg_route_ensure.yml` — idempotent in-band repair; imported by `preflight.yml`,
  `deploy_backend.yml` and around every package stage of the bootstrap playbooks. Never restarts a
  healthy tunnel, never touches keys/config.
- `bootstrap_nat.yml` now installs the permanent fix on pp-back: networkd drop-in
  (`ManageForeignRoutes=no`, `ManageForeignRoutingPolicyRules=no`), `/usr/local/sbin/pp-wg-routes`,
  `pp-wg-route-guard.timer` (30 s), a `wg-quick@wg0` drop-in (`ExecStartPost`) and an apt
  `DPkg::Post-Invoke` hook.
- Fresh-server chicken-and-egg solved: temporary MASQUERADE for 10.0.0.0/16 on pp-front + temporary
  default route via 10.0.0.2 on pp-back → `apt install wireguard` → tunnel up → temporary path removed
  (`-e keep_private_nat=true` keeps it).
- `ansible/tasks/infra_defaults.yml` — every non-secret infra var has a central default;
  `frontend_public_ip` is derived from `hostvars[groups['frontend'][0]].ansible_host`. Fixes the
  undefined `frontend_public_ip` / `ssl_cert_path` / `ssl_key_path` in preflight. Imported by every
  play. Offline check: `playbooks/selftest_defaults.yml`.
- New `bootstrap/bootstrap_frontend_base.yml` (nginx + Node/yarn + web root + TLS dir) — a fresh
  server never needs a manual `apt install nginx`. `deploy_frontend.yml` installs nothing any more,
  it only asserts the toolchain and points at the bootstrap playbook.
- `bootstrap_firewall.yml`: added `ufw routed policy allow` + WireGuard subnet, and a backend egress
  re-check after the firewall change.
- `ansible.cfg` was never committed (untracked) — now in the repo, and the removed
  `community.general.yaml` stdout callback replaced with `stdout_callback=default` + `result_format=yaml`
  (ansible-core ≥ 2.19 refused to start otherwise). `requirements.yml` added for community.general +
  ansible.posix.
- `wg0-front.conf.j2` uses `wg_subnet` instead of an inline regex.
- WireGuard endpoint stays `10.0.0.2:51820` (asserted in `infra_defaults.yml` and in the tests).
- `site.yml` is still application-only: preflight → backend → frontend → nginx.

### Desired flow (documented in deploy/hetzner/README.md)
`git pull` → `ansible-playbook playbooks/preflight.yml` → `ansible-playbook playbooks/site.yml -e ref=main`.
No local edits, no stash, no manual routes/nginx. One-time on the live pair: run
`playbooks/bootstrap/bootstrap_nat.yml` to install the route guard.

### Tests
`backend/tests/test_deploy_config.py` (36 static guards: routine playbooks install nothing, every play
imports infra_defaults, guard + temp-NAT + networkd fix present, all templates render with
StrictUndefined) and `backend/tests/test_wg_route_guard.py` (2 functional tests with faked `ip`/
`systemctl`: repairs the exact production state, no-ops when healthy). All 38 pass.
`ansible-playbook --syntax-check` clean for every playbook; `selftest_defaults.yml` passes with no
`group_vars/all.yml` at all.

### 2026-06 — pip stage: requirements path is discovered, not assumed
`deploy_backend.yml` no longer hardcodes `deploy/requirements-prod.txt` (the deployed `main` did not
contain it → `Errno 2`). It now stats `prod_requirements_candidates`
(`deploy/requirements-prod.txt`, `backend/requirements-prod.txt`, `requirements-prod.txt`,
`deploy/hetzner/requirements-prod.txt`), uses the first that exists, and otherwise derives a portable
list from `backend/requirements.txt` minus `platform_only_packages` (`emergentintegrations`) into
`{{ env_dir }}/requirements-prod.generated.txt` — byte-identical to `deploy/requirements-prod.txt`.
If nothing is found it fails with the exact paths it looked for. Verified locally with ansible-playbook
(both branches + idempotent rerun) and by 2 new pytest cases (40 deploy tests total).

### 2026-06 — deploy dry-run harness (`deploy/hetzner/dryrun.py`)
Offline validation of every deploy artefact with the real tools: renders all 8 Jinja templates with
StrictUndefined, `systemd-analyze verify` on the backend unit + route-guard units, `nginx -t` on the
rendered site config for BOTH http2 variants (asserting the version switch in deploy_nginx.yml is
right), `bash -n` on the route guard, backend.env vs. every `os.environ[...]` key in backend/*.py,
`--syntax-check` on all 12 playbooks and `pip install --dry-run -r deploy/requirements-prod.txt`
(all 133 pins resolve). All green.

Additionally the backend was booted exactly as systemd will boot it (release copy + rendered
backend.env, single uvicorn worker): `/api/settings`, `/api/products`, `/api/collections`,
`/api/sitemap.xml`, `/api/robots.txt`, `/api/link-index`, `/api/nextcart/countries`,
`/api/nextcart/config`, `/api/nextcart/pickups` (589 Econt offices), admin login + `/api/admin/orders`
+ `/api/admin/analytics` and a **full bank-transfer order** (order BEM72, deleted afterwards) — all OK.

**Bug found and fixed:** `group_vars/all.yml.example` had `nextcart_base_url:
https://client.nextcartmanager.com`, which answers 404 → `/api/nextcart/*` returned 502 and the whole
checkout/courier flow would be dead in production. Correct host: `https://api.nextcartmanager.com`.
Guarded by a test, and `deploy_backend.yml` now verifies `/api/nextcart/countries` and
`/api/products?locale=bg` after the restart, so a wrong value fails the deploy instead of the shop.
⚠️ The owner's local (gitignored) `group_vars/all.yml` must be checked for the same wrong value.
Deploy test suite: 52 pytest cases green.

### 2026-06 — requirements file: committed + release-wide search
- `deploy/requirements-prod.txt` regenerated with a documented header (133 pinned packages,
  `backend/requirements.txt` minus `emergentintegrations`) so it is part of the next commit and lands
  on GitHub `main`. It was already tracked (commit a596773) — the failing server checkout means the
  pushed ref did not contain it.
- `deploy_backend.yml`: the requirements lookup is now a recursive `find` over the whole release
  (`requirements-prod.txt` wins anywhere, then `backend/requirements.txt` → portable copy), it asserts
  `backend/server.py` exists right after the checkout (detects a wrong repo layout immediately) and the
  failure message prints the top level of the checkout plus everything the search found.
- Verified locally with ansible-playbook for 4 layouts: prod file in `deploy/`, prod file nested in
  `app/deploy/`, only `backend/requirements.txt` (portable copy generated, idempotent) and an empty
  checkout (clear failure listing `docs, frontend`). New pytest guards: file is tracked by git, every
  dependency pinned, no platform-only package, core packages present. 54 deploy tests green.

### 2026-06 — deploy adapts to the repository layout + hard diagnostics
The server checkout of GitHub `main` contained **no `backend/server.py`** (the assert added in the
previous step caught it). Since the app cannot be deployed from a ref that does not contain it:
- `deploy_backend.yml` locates `server.py` recursively (depth 4) and derives `backend_src_dir` /
  `backend_rel_path`; `.env` symlink, `.image_cache`, the media-import chdir and the systemd unit
  (`WorkingDirectory`, `ReadWritePaths`) all use them, so a nested layout (`app/backend/…`) deploys too.
  `backend_rel_path` defaults to `backend` in `tasks/infra_defaults.yml`.
- `deploy_frontend.yml` does the same for `frontend/package.json` (`frontend_src_dir`, node_modules
  filtered out).
- When the app is not in the ref at all, the failure message now prints the **actual contents of the
  checkout** (two levels) so the cause is obvious instead of "Unknown error".
- Verified locally with ansible-playbook for: standard layout → `backend`, nested → `app/backend`,
  empty repo → clear failure listing the files. 55 deploy tests + full dryrun green.

### 2026-06 — ROOT CAUSE of the "(empty) checkout": lookup() in play vars
`deploy_backend.yml` had `release_stamp: "{{ lookup('pipe', 'date +%Y%m%d%H%M%S') }}"` inside `vars:`.
Ansible re-evaluates a lookup on **every reference**, so `release_dir` differed per task: git cloned
into `main-…230942` while the following tasks inspected `main-…230943` → empty listing, "no
requirements file", "no backend/server.py". Same bug for `build_stamp`/`src_dir` in
`deploy_frontend.yml`.
Fix: both directories are frozen once with `set_fact` in `pre_tasks` (and printed). Proven locally
(vars lookup returns two different values, set_fact one) and e2e: cloning the real
`https://github.com/martingtodorov/PP.git` main into a temp release and running the detection block
finds `backend` layout + `deploy/requirements-prod.txt` (133 pins, correct header, corrected
`nextcart_base_url`). GitHub main is complete — the repo was never the problem.
Guard: `test_release_directories_are_frozen_with_set_fact`. 56 deploy tests + dryrun green.

### 2026-06 — requirements-prod.txt rewritten as a MINIMAL list (py3.14 compatible)
pp-back runs **Python 3.14**. The old file was a `pip freeze` of the dev pod (133 pins incl.
google-*, litellm, openai, pandas, numpy, boto3, black, mypy, pytest, stripe) and pip failed with
`ResolutionImpossible`: google-api-core[grpc] 2.30.2 needs grpcio-status>=1.75.1 on py3.14 while the
freeze pinned 1.71.2. pymongo==4.5.0 also has no py3.14 wheel.
New file: **19 top-level pins** — only what backend/*.py imports (fastapi, starlette, uvicorn,
pydantic, email-validator, python-multipart, python-dotenv, motor==3.7.1, pymongo==4.15.5, PyJWT,
bcrypt, httpx, requests, resend, anthropic, pillow, openpyxl, pywebpush) with transitive deps left to
pip. Verified with `pip install --dry-run --python-version 3.14 --only-binary=:all:` (37 packages
resolve; http-ece is source-only and builds with build-essential).
Runtime verified: fresh venv with exactly this list boots the backend from a rendered production
`backend.env`; 200 on settings/products/collections/articles/sitemap/robots/link-index/locales/pages,
nextcart countries+config, admin login + orders/customers/analytics/settings/abandoned-carts/inventory,
WebP image negotiation, `/api/cart/track`, `/api/track` and a **full COD order** (GYA41, cleaned up)
— all on motor 3.7.1 / pymongo 4.15.5.
`deploy_backend.yml`: the `backend/requirements.txt` fallback was REMOVED (installing the dev freeze
would reintroduce the conflict); it now requires a `requirements-prod.txt` anywhere in the release and
fails with a precise message. Tests: `test_requirements_portable.py` now derives the required packages
from the actual imports, forbids the pip-freeze packages and caps the list at 25 pins. 58 deploy tests
+ full dryrun green. **No server change needed — do NOT downgrade Python on pp-back.**

### 2026-06 — backend crash-loop cause: MongoDB was never installed/started on pp-back
Journal showed `pymongo.errors.ServerSelectionTimeoutError: localhost:27017 Connection refused` in
`on_startup → ensure_indexes()`, so uvicorn exited and the health check got "Connection refused".
MongoDB had never come up because the earlier `bootstrap_backend_base.yml` run died at the MongoDB
apt key (the WireGuard routing bug).
Changes:
- `preflight.yml` now waits for 127.0.0.1:27017 on pp-back and fails with the exact command
  (`bootstrap_backend_base.yml --tags mongo`) instead of letting the deploy crash-loop later.
- `bootstrap_backend_base.yml`: the MongoDB apt repo codename is resolved through
  `mongo_supported_codenames` (focal/jammy/noble) with `mongo_repo_fallback_codename: noble`, prints
  which repo it uses, waits for port 27017 after starting mongod and dumps `journalctl -u mongod` when
  it does not come up.
- `deploy_backend.yml` health check now hits `/api/settings` (there is no `GET /api/` route — the old
  check would 404 forever) and on failure prints `systemctl status` + 60 journal lines.
47 deploy-config tests green.

### 2026-06 — MongoDB repo is probed, not guessed
`mongodb-org 7.0` has no `noble` packages (and pp-back runs an even newer Ubuntu), so the apt cache
update failed with "does not have a Release file". `bootstrap_backend_base.yml` now HEAD-probes
`https://repo.mongodb.org/apt/ubuntu/dists/<codename>/mongodb-org/<major>/Release` for
`mongo_major_candidates` (8.0, 8.2, 7.0) × [distro codename, noble, jammy], uses the first that
returns 200, fetches the matching `server-<major>.asc` key and prints the choice. Fails with the full
probe list if MongoDB publishes nothing usable.
Verified live against repo.mongodb.org: Ubuntu resolute → **8.0 / resolute**, plucky → 8.0 / noble
(7.0/noble correctly 404s). 61 deploy tests + dryrun green.

### 2026-06 — stale mongodb-org.list removal
The failed 7.0/noble repo stays in `/etc/apt/sources.list.d/mongodb-org.list` and poisons EVERY
`apt update` on pp-back. `bootstrap_backend_base.yml` now deletes that file (and the .sources variant)
before probing, refreshes the cache, adds the probed repo with `update_cache: false` and refreshes the
cache in a separate retried task. 48 deploy-config tests green.
NOTE: the owner ran an older checkout (error at line 80 with 7.0/noble) — the fixes only reach the
server after "Save to GitHub" + `git pull` on the Mac.

### 2026-06 — MongoDB probe now checks the PACKAGE INDEX, not just the repo
`dists/resolute/mongodb-org/8.0/Release` returns 200 but that component ships only
`mongodb-database-tools` — no `mongodb-org-server` — so `apt install mongodb-org` failed. The probe now
greps `.../multiverse/binary-amd64/Packages` for `^Package: mongodb-org-server$` and picks the first
repo that really has the server. Verified live: resolute → **8.0 / noble** (noble 8.0 has 28 server
builds; deps libssl3t64/libcurl4t64 exist on 24.04+). `Install mongodb-org` got a rescue that prints
`apt-get install -s mongodb-org` so unmet dependencies are visible instead of hidden behind retries.
49 deploy-config tests green.

### 2026-06 — MongoDB 8.x does not start on Linux >= 6.19 (SERVER-121912)
mongod exited immediately: "Linux kernel versions 6.19 and newer has a known incompatibility with this
version of MongoDB". Cause: the TCMalloc vendored into MongoDB 8.x is incompatible with the new
restartable-sequences (rseq) behaviour; **no patched MongoDB release exists** (8.0/8.2 all affected).
Upstream workaround, now applied by `bootstrap_backend_base.yml`:
`/etc/systemd/system/mongod.service.d/10-pp-rseq.conf` with
`Environment=GLIBC_TUNABLES=glibc.pthread.rseq=1` (rseq=0 causes memory corruption), followed by
daemon-reload + restart when the drop-in changes. Guarded by
`test_mongodb_kernel_workaround_is_applied`. 50 deploy-config tests green.

### 2026-06 — single-worker assertion fixed + MongoDB running
The backend deploy now gets past the health check (`/api/settings` answers). The old check
`pgrep -fc 'uvicorn server:app'` always returned 2, because uvicorn with `--workers 1` runs a
supervisor process plus one worker. It now reads `--workers` from the unit's ExecStart and counts the
children of MainPID (`pgrep -P`), failing only on a real multi-worker setup. Verified with a simulated
matrix (1/1, 1/0 pass; 1/4, 4/4 fail).
MongoDB is `active` on pp-back after the rseq drop-in (kernel 7.0.0-30, Ubuntu 26.04 LTS).
51 deploy-config tests green.

### 2026-06 — NextCart host auto-corrected in the deploy
The server's rendered backend.env still carried `NEXTCART_BASE_URL=https://client.nextcartmanager.com`
from the owner's (gitignored) group_vars/all.yml → `/api/nextcart/countries` returned 502
("Услугата за доставки върна грешка") and the courier verification failed. `tasks/infra_defaults.yml`
now rewrites that dead host to `https://api.nextcartmanager.com` (with a warning) and defaults to it
when unset, so a stale vault file cannot break the checkout. The courier verification in
deploy_backend.yml gained a rescue that prints the NEXTCART_* lines from backend.env plus the upstream
HTTP status. Verified with a real playbook run (client → api). 52 deploy-config tests green.

### 2026-06 — courier check downgraded to a warning (owner's decision: ship first)
`/api/nextcart/countries` still 502s on pp-back even after the host correction (upstream refuses the
server; to be investigated later). Per the owner's instruction the courier verification in
`deploy_backend.yml` now prints the full diagnostics (NEXTCART_* env lines + upstream HTTP status) as a
WARNING and continues, so the site can go live. `-e require_couriers=true` turns it back into a hard
gate. The catalog check stays fatal.
**OPEN P1: checkout/couriers are broken in production** — `/api/nextcart/*` returns 502 from pp-back
while the same code works from the preview pod, so it is environment/upstream specific (candidate
causes: NextCart rejecting the server's egress IP 2.28.79.24, or a missing shop credential in
group_vars/all.yml).

### 2026-06 — NextCart 403 solved with a committed snapshot (P0 CLOSED)
The Hetzner egress IP is rejected by `api.nextcartmanager.com` with **403 Forbidden** (not a URL or
credential problem — the same code works from the preview pod). The checkout no longer depends on the
upstream:
- `backend/data/nextcart/` now ships **23 snapshot JSON files**: `config_XX.json` for all 11 shipping
  countries + `offices_XX_<courier>_<dest>.json` (BG econt/office 589, BG econt/locker 41,
  BG boxnow/locker 926, BG pigeon/office 186, RO fancourier/locker 3194, GR speedex/office 968,
  HU 914, PL 5000, SK 763, SI 607, HR 185, DE 5000 GLS offices). CZ and IT sell address-only upstream.
- `backend/nextcart.py`: new `_snapshot()` + `_get_or_snapshot()`. `/config`, `/pickups`, `/offices`
  and `_probe_pickups` fall back to the snapshot on any upstream failure; `/offices` filters `q` and
  `limit` locally. `/address-suggestions` returns `{"suggestions": []}` instead of 502 (no snapshot is
  possible for a free-text database — the customer types the address manually, owner's choice).
- New env flag **`NEXTCART_SNAPSHOT_ONLY`** (rendered by `templates/backend.env.j2`, defaulted to
  `true` in `tasks/infra_defaults.yml` and `group_vars/all.yml.example`): production reads the files
  directly, without burning a timeout per request. Set to `false` to go back to live upstream.
- `frontend/src/components/PreCheckoutModal.jsx`: the street `AddressSuggest` was missing
  `onChangeText`, so with an empty suggestion list `addr.street` never filled and the place-order CTA
  stayed disabled — fixed.
- Refresh the snapshot from a machine that can reach the API:
  `python backend/scripts/refresh_nextcart_snapshot.py` (now covers office **and** locker lists).
Tested: iteration_22 (backend 26/26 pytest, 3/4 frontend) and iteration_23 (address flow 3/3 —
BG/Pigeon COD order placed, GR/Speedex and DE/GLS address CTA enabled). Test orders removed from the DB.

**Remaining backlog**
- P1: RevOrder webhook sync — blocked, waiting for the NextLevel webhook URL from the owner.
- P2: verify `purepeptide.bg` in the Resend dashboard (emails stay in sandbox until then).
- P2: Apple/iOS Safari autofill verification in the checkout.

### 2026-06 — couriers can no longer fail a deploy
Both failing Ansible tasks (`Wait for the courier endpoint` on pp-back and `Public API smoke test` on
pp-front) curl the SAME url: `/api/nextcart/countries`.
- `deploy_nginx.yml`: the fatal smoke test now hits `/api/settings` (it verifies nginx → backend
  routing, which is what that playbook owns); the courier call became informational (`failed_when:
  false`) with a warning.
- `backend/nextcart.py`: `/nextcart/countries` never raises any more — when neither the upstream nor a
  snapshot answers it returns the 11 shipping countries from static `COUNTRY_NAME_BG` /
  `COUNTRY_DIAL` maps, so the checkout country selector always renders. `/nextcart/event` no longer
  propagates a config failure either.
- `deploy_backend.yml` rescue now prints whether the release contains `data/nextcart` (file count),
  the `NEXTCART_SNAPSHOT_ONLY` line from backend.env and the deployed commit — so the next failure is
  self-diagnosing.
- `tests/test_iteration16_nextcart.py::test_city_suggest` relaxed: an empty suggestion list is the
  contract in snapshot-only mode. 123 nextcart/deploy tests green.

### 2026-06 — deploy verification decoupled from DNS + canonical_domain
`Public API smoke test` failed because it requested `https://purepeptide.bg/api/settings` — that
domain still resolves to the **old Shopify store** (404, `server: cloudflare`). The deploy itself was
fine (pp-back failed=0, pp-front 50 ok).
- `deploy_nginx.yml`: the fatal check now asks the LOCAL nginx with a Host header
  (`curl -k https://127.0.0.1/api/settings -H 'Host: {{ canonical_domain }}'`), so it validates
  nginx → backend regardless of DNS. Added an informational per-domain table (HTTP status +
  `server:` header) that shows which of site_domains still point at Shopify, plus a non-fatal
  courier check through the same local route.
- New var **`canonical_domain`** (`tasks/infra_defaults.yml`, defaults to `site_domains[0]`, asserted
  to be inside site_domains) drives `REACT_APP_SITE_URL` in `deploy_frontend.yml` and the deploy
  checks. Owner's choice (option c) so the canonical host can change without reordering site_domains.
  `group_vars/all.yml.example` now sets `canonical_domain: purepeptide-labs.bg`.
- Note: sitemaps / hreflang / robots are NOT affected by site_domains — they are built from the
  per-locale origins (`i18n.SITE_ORIGINS`, overridable via the `site.locale_routes` admin setting),
  so every domain already has its own sitemap.
102 nginx/deploy/nextcart tests green.

### 2026-06 — ROOT CAUSE of the Cloudflare 521: handlers never ran
`ss -ltnp` on pp-front showed nginx listening on **:80 only**, while `nginx -T` already contained
`listen 443 ssl` for all five domains — and `journalctl -u nginx` had no reload after 06:09 UTC.
Ansible handlers run at the END of a play: every earlier run aborted on the verification task, so the
`reload nginx` handler was never reached, the freshly enabled `purepeptide.conf` was never loaded and
Cloudflare got a refused connection (521). The site had been down since.
- `deploy_nginx.yml` / `deploy_backend.yml`: `meta: flush_handlers` before the verification block.
- `deploy_nginx.yml`: new self-healing task **"nginx must be listening on 443"** — if no `:443`
  socket exists it restarts nginx and waits for the socket (covers a master process that predates the
  config).
- Verification now uses `curl --resolve` against 127.0.0.1 / private IP / public IP, prints
  `ss -ltnp` on every run and dumps `nginx -T`, `systemctl status nginx` and all attempts on failure.
- 5 new guards in `tests/test_deploy_config.py` (flush_handlers before verify, 443 self-heal, no
  public-DNS dependency, canonical_domain, courier snapshot shipped). 57 deploy tests green.

### 2026-06 — production verified live (purepeptide-labs.bg)
nginx opened :443 after the flush_handlers/self-heal fix and the site is up. Checked from outside:
`/api/settings` 200, `/api/products?locale=bg` 200 (catalog non-empty), `/` 200,
`/api/nextcart/countries` 200 with 11 countries, `/api/nextcart/config?country=BG` returns
econt/office €3.89 + boxnow/locker €2.99 + pigeon/address €4.59, `/api/nextcart/pickups`
(BG/econt/office) returns **589 offices** — i.e. the courier snapshot works on the blocked server.
Remaining fix in this round: the smoke/courier tasks no longer echo the raw response body
(`head -c` cut a Cyrillic character mid-byte → "Refusing to deserialize an invalid UTF8 string
value" killed the task even though nginx answered 200). They now print status + size, an ASCII-only
country count, and the one remaining `head -c` in deploy_backend.yml is piped through `iconv -c`.
58 deploy tests green.

### 2026-06 — real catalog + catch-all collection hidden on the homepage
Diagnosis: **production was still running the demo seed data** (16 products with 430–1200 char
descriptions, 7 seed collections with handle `all-peptides`, no `catalog_imported` flag), which is why
the homepage showed a "Всички пептиди" card that 404s (the code canonicalises to
`2all-the-peptides-1`) and why the descriptions were short.
- `frontend/src/lib/collections.js` (new): `ALL_COLLECTION` + `isAllCollection()` matching BOTH the
  Shopify handle and the legacy seed handle. Used in HomePage, StaticPage, ProductPage,
  AdminProductEditPage and HtmlSitemapPage — the catch-all card can no longer appear regardless of
  which handle the database carries.
- `backend/matrixify_import.py`: `ALL_HANDLE` is now `2all-the-peptides-1` (must equal
  `server.ALL_COLLECTION`, otherwise the catch-all collection page 404s); published collections with 0
  products (SEO landing pages like `retatrutide-price`) are imported as `nav_hidden` instead of being
  dropped.
- `backend/server.py` `/link-index`: skips `nav_hidden` collections so hidden landing pages stay out
  of the HTML sitemaps.
- `deploy_backend.yml`: new gated task — `-e run_catalog_import=true` runs
  `matrixify_import.py --only collections,products,pages,articles,redirects,discounts` on the server
  (customers are deliberately NOT a default step: that importer step wipes the customers collection).
  The importer sets `catalog_imported`, so `seed_catalog()` never overwrites the real data again.
- Local import verified: 23 products with full Body HTML (bpc-157-5 → 8269 chars,
  21-retatrutide-5 → 1886), 8 collections, 12 pages, 19 articles, 15 redirects, 22 discounts.
- Tested: iteration_24 frontend run 100% (homepage carousel = the 6 topic collections only, hero CTA
  and "Виж всички" open the 23-product catch-all page, long descriptions render, admin edit works).
  62 deploy tests green.

**Production TODO (owner):** after Save to GitHub + `git pull`, run
`ansible-playbook playbooks/deploy_backend.yml -e run_catalog_import=true` once — without it prod
keeps the 16 demo products.

### 2026-06 — broken images after the Matrixify import (nginx regex precedence)
Owner ran the catalog import on production (23 products live) and every product image 404'd.
Root cause: **nginx evaluates regex locations BEFORE prefix locations**, so
`location ~* \.(png|jpe?g|webp|svg|gif|ico|woff2?)$ { try_files $uri =404; }` captured every
`/api/files/import/*.png` and answered with nginx's own 404 (162 bytes, text/html). It never showed
before because the seed catalog pointed at absolute Shopify CDN URLs; imported media is local.
- `templates/nginx-purepeptide.conf.j2`: `location ^~ /api/` and `location ^~ /api/files/` — `^~`
  stops the regex evaluation. **Proven locally** with a real nginx in the pod + stub backend:
  old config → 404, fixed config → 200 with the backend's body.
- `server.py` `get_collection`: the catch-all collection now resolves under BOTH handles
  (`2all-the-peptides-1` and legacy `all-peptides`), so the hero CTA / "Виж всички" cannot 404 on a
  database imported with the older script. Verified: both handles → 200 with 23 products.
- New guard test; 61 deploy tests green.

**Production TODO (owner), in this order:** Save to GitHub → `git pull` →
`deploy_nginx.yml` (fixes the images) → `deploy_frontend.yml` (hides the "Всички" card) →
`deploy_backend.yml -e run_catalog_import=true` (re-import so the catch-all handle becomes the
canonical `2all-the-peptides-1`).

### 2026-06 — Matrixify import fills every meta title / meta description
`matrixify_import.py` now has `meta()` (reads BOTH metafield column types — the Blog Posts sheet
carries `Metafield: title_tag [string]` AND `[single_line_text_field]`) and `seo_pair()`, used by the
collections, products, pages and articles importers. Fallback chain: metafield → record title for the
meta title, metafield → first 160 chars of the body text → title for the meta description.
After the re-import: **0 records without a meta title or description** (23 products, 8 collections,
19 articles, 18 bg pages). Only the non-bg page copies still lack SEO — those are AI translations made
before the SEO data existed; re-running the page translation in the admin fills them.
New test file `backend/tests/test_matrixify_seo.py` (7 tests) + 61 deploy tests → 68 green.

### 2026-06 — page texts + broken images (root causes) 
Owner: "импортите от матриксифай не работят, текстовете от страниците не се импортират и снимките не
работят". Both were real and both had a precise cause:
1. **Pages**: `PAGE_MAP` made the importer write to slugs the app never opens. The storefront routes
   on the **Shopify handles** (`pages_seed.PAGE_SLUGS` = `terms-conditions`, `delivery-and-payment`,
   `какво-са-пептиди`…), while the import filled `terms-of-service`, `shipping-policy`,
   `what-are-peptides`… so /pages/terms-conditions kept its 199-char seed stub. It also imported only
   the 11 PAGE_MAP handles. `import_pages()` now imports EVERY row of the sheet under its Shopify
   handle (skipping `html-sitemap*`, empty bodies) and publishes the PAGE_MAP slug as an alias
   carrying `canonical_slug` (kept out of /link-index and /api/links).
2. **Images**: `db.image_map` cached `src -> /api/files/...` forever. On the fresh server the media
   directory was empty, the importer trusted the cache, never re-downloaded, and published URLs that
   404'd. `store_image()` now verifies the file is really in storage (`_stored_ok()`) before reusing a
   mapping; `files`/`image_map` writes became idempotent upserts. Local audit after the fix: 0 missing
   media files across products, collections, pages and articles.
   Bonus: `clean_body()` strips `<script>` (the Shopify opt-out page shipped an hCaptcha script).

### 2026-06 — full local currency for CZ/HU/PL/RO (owner's choices)
Prices stay in EUR in the database; the CZ/HU/PL/RO storefronts are shown, charged, e-mailed and
recorded in their own currency. BG keeps € + BGN dual pricing, other euro countries unchanged.
- `backend/currency.py`: `LOCALE_CURRENCY`, ECB daily feed (`eurofxref-daily.xml`) with a Mongo
  snapshot (`fx_rates`) + 6h memory cache + static fallback, `nice_price()` (psychological rounding:
  <100 → ceil, <1000 → next x9, ≥1000 → next xx90) and `order_amounts()` (totals are built from the
  rounded line prices, percentage discounts apply to the local subtotal).
- `GET /api/currency?locale=` serves currency + dated rate; checkout stores `currency`,
  `currency_rate`, `*_orig` and `items[].price_orig` (the admin already renders those).
- E-mails: `_money(v, cur)` / `_money_of(order)` — customer and admin mails are fully in RON/CZK/…;
  the bank-transfer block adds the EUR amount because the IBAN is a euro account. Push notification
  uses the local total.
- Frontend `lib/money.js` mirrors the backend rule: `amountOf`, `fmtAmount`, `fmtPrice`,
  `cartAmounts()` — cart, checkout, modal and success page all render from `cartAmounts`, which fixed
  the 349-vs-351 lei drift found in iteration_25. `schema.js` emits the local `priceCurrency`.
- Verified live: 29 EUR → 159 RON / 709 CZK / 22 990 HUF everywhere; a real RON order recorded
  638 RON and the mail rendered `318 lei / 21 lei / 339 lei`.

### 2026-06 — every internal link is dynamic
Owner: renaming Общи условия or Retatrutide must not break the site.
- `backend/links_map.py`: `LINK_TARGETS` (15 logical keys) + `link_key_for()`; the importer stamps
  `link_key` on pages and collections.
- `GET /api/links?locale=` resolves each key: the doc carrying `link_key` first (so a rename follows
  automatically), then the known handles; aliases are never returned. 5-minute cache, invalidated
  when a page or collection is saved in the admin.
- `frontend/src/lib/links.js` holds the defaults and `link(key)`; `LocaleContext` hydrates it from the
  API. Every hardcoded `/pages/...` / `/collections/2all-the-peptides-1` in the storefront is gone
  (guarded by a test). Proven by renaming `terms-conditions` → `obshti-usloviya` and
  `retatrutide-price` → `retatrutide-5mg-10mg`: /api/links followed both instantly.
- Tests: `tests/test_local_currency.py` (7), `tests/test_dynamic_links.py` (7),
  `tests/test_iteration26_review.py` (15) — all green, iteration_26 report 100%.

**Open item (offered, not built):** the cart/checkout/modal UI strings are still Bulgarian on the
non-BG storefronts (product data and nav are translated, the checkout chrome is not).

**Production TODO (owner):** Save to GitHub → `git pull` → `ansible-playbook -i inventory.ini
playbooks/deploy_backend.yml -e run_catalog_import=true` (re-import to fix the page texts and the
missing media) → `deploy_frontend.yml` → `deploy_nginx.yml`. Note: always pass `-i inventory.ini`.

### 2026-06 — "images still broken": the cache was poisoned, the origin was already fine
Measured in a clean browser on production: homepage 57 images / collection 32 / product 19 — only
**2** were broken (`4961a3f6bac6-retatrutide_5mg…png`, `74752aefec3e-ad1dd308d7c2d2f6dc53.png`), i.e.
two files an earlier import left dangling; the `_stored_ok()` fix re-downloads them on the next
import. What the owner sees is a **cached** 404: while the static-image regex was swallowing
`/api/files/*.png`, nginx answered 404 AND attached `Cache-Control: public, max-age=2592000` /
`max-age=31536000, immutable`, because every `add_header` in the template used `always` (which applies
the header to error responses too). Cloudflare and every visitor's browser therefore keep serving the
broken image for up to a year.
- `templates/nginx-purepeptide.conf.j2`: `always` removed from the three long-lived Cache-Control
  headers (nginx's own `expires` only touches successful statuses). **Proven with a real nginx**
  rendered from the template: media 200 → `immutable`, media 404 → no Cache-Control at all, static
  and image-regex 404 → no Cache-Control.
- `frontend/src/lib/api.js`: `img()` now appends `&v=${MEDIA_REV}` (MEDIA_REV=2) so the new build
  requests fresh cache keys and bypasses whatever is already poisoned, without waiting for a purge.
- 2 new guard tests (63 deploy tests green).
**Owner action:** purge the Cloudflare cache (Caching → Configuration → Purge Everything) once, then
deploy nginx + frontend + the catalog re-import.

### 2026-06 — IP geo в чекаута: причината беше самият IP-град
Собственик докладва: "в Созопол съм, показва офиси до Велико Търново".
Измерено: `ipwho.is` **и** `ip-api.com` връщат `Sofia` (центроида на страната) за всеки български IP,
независимо от ISP — city-level IP геолокацията у нас е безполезна, а грешният град е по-лош от липсващ.
- `backend/geo.py`: `/geo/country` вече връща само държава + `city: ""` (и информативно `ip_city`).
  `/geo/reverse` (Nominatim, fallback city→town→village→municipality) дава истинския град по
  координати на устройството: 42.4185,27.6957 → `Созопол` 8130.
- `frontend/src/lib/checkoutPrefetch.js`: нов `pfDeviceGeo({prompt})` — navigator.geolocation →
  `/geo/reverse`, кеш 30 мин в `pp_geo_device_v1`.
- `PreCheckoutModal.jsx`: `locate()` при отваряне; ако няма разрешение — градът остава ПРАЗЕН
  (изборът на собственика) и се показва бутон `pc-locate-btn` "Намери най-близките до мен".
- Проверено (iteration_27, 100%): Созопол → placeholder "най-близки до Созопол", първите 4 офиса са в
  Созопол; Велико Търново → същото; без geo — нищо не се предполага.

### 2026-06 — задрасканата цена на Ретатрутид
Причина: Matrixify експортът държи "was" цената в market колоната **`Compare At Price / Bulgaria`**
(`Variant Compare At Price` е празна), а импортът я игнорираше напълно.
- `matrixify_import.py`: варианти вече четат `Variant Compare At Price` → fallback
  `Compare At Price / Bulgaria` в `compare_at_eur`; съществуващата база е backfill-ната.
- Резултат: 5mg 49/59 €, 10mg 89/99 €, 30mg 159/179 € — задраскана цена + процент отстъпка на
  продуктовата страница, в StickyBuyBar и в картите в колекциите. Само Ретатрутид има такива цени в
  експорта (проверени 40 продукта — без регресия).
- Тестове: `backend/tests/test_iteration27_geo_and_compareat.py` (13 зелени).

**Отворено (P1):** RevOrder webhook (чака URL от собственика), верификация на `purepeptide.bg` в
Resend, UI низовете на чекаута за не-BG магазините.

### 2026-06 — RevOrder: ключовете се издават от нас и се виждат в админа
Собственик: „Създай webhook url, secret key и api key… искам да се виждат в админ панела.“
- `backend/revorder.py`: `POST /api/admin/integrations/revorder/generate` издава `api_key`
  (`pp_live_<32hex>`) + `secret_key` (64 hex); `GET …/reveal?domain=` дава пълните стойности само на
  админ сесия; списъкът винаги е маскиран. `webhook_url()` = `PUBLIC_SITE_URL` ако е зададен, иначе
  `https://<домейн>` (в продукция `public_site_url` е празен → всеки домейн получава своя адрес).
- **purepeptide-labs.bg**: остава псевдоним на purepeptide.bg (`DOMAIN_ALIASES`) — ползва същите
  ключове, но има собствен webhook адрес, който се показва в картата. Проверено: подписан POST на
  `/api/webhooks/revorder/purepeptide-labs.bg` → 200.
- Нов екран `/admin/integrations` (`AdminIntegrationsPage.jsx`, меню „Интеграции“): по карта за
  .bg/.eu/.ro/.gr — webhook URL, маскирани ключове с „Покажи“/копиране, „Генерирай нови“,
  превключвател „Изпращай поръчките“, RevOrder API адрес (`https://api.nextcartmanager.com`) + път,
  „Тествай връзката“ и журнал на събитията.
- Входящите webhook-ове се проверяват с HMAC-SHA256 върху secret key-а, идемпотентни по event id;
  обновяват `fulfillment_status` / `tracking_number` на поръчката.
- Тестове: `tests/test_iteration28_revorder.py` (18 зелени), iteration_28 отчет.
  Всички домейни са оставени ИЗКЛЮЧЕНИ — собственикът ги пуска, щом ключовете са в RevOrder.

### 2026-06 — Origin сертификат за всеки домейн (SNI)
Дотогава nginx имаше един server блок с една двойка `origin.pem/key` за всички домейни, а всяка
Cloudflare зона издава свой Origin сертификат — сертификат за purepeptide.bg не може да обслужва
purepeptide.ro.
- `group_vars/all.yml.example`: нов `site_tls_certs: {}` — карта домейн → `cert`/`key` (файловете се
  качват ръчно, playbook-ът никога не генерира TLS). Домейн без запис ползва общата двойка.
- `templates/nginx-purepeptide.conf.j2`: рендерира по един 443 server блок за всяка двойка
  сертификати (общото тяло е Jinja макрос), nginx избира правилния през SNI.
- `playbooks/deploy_nginx.yml`: проверката за съществуващи сертификати обхожда общата двойка + всички
  от `site_tls_certs`.
- Проверено с истински nginx: `nginx -t` минава и с една, и с три различни двойки; 68 deploy теста
  зелени.

### 2026-06 — количката и чекаутът говорят езика на клиента
Собственик: „Преведи текстовете в количката и чекаута за RO/PL/CZ/HU“ + „екран в админа за редакция“
+ „AI превод“ + „кой бутон превежда абсолютно всичко“.
- `frontend/src/i18n/checkoutStrings.js` (нов): 93 текста × 11 езика (bg, en, ro, pl, cz, hu, de, fr,
  sk, si, gr) — ръчно написани, не машинни. `locales.js` ги слива в речника и `translate()` вече
  поддържа заместители: `{amount}`, `{code}`, `{city}`, `{courier}`.
- Пренаписани без нито един твърдо зашит български текст: `CartPage`, `CheckoutPage`,
  `CheckoutSuccessPage`, кошницата в `Layout`, `PreCheckoutModal`. Куриерите излизат на латиница
  извън BG магазина (`Econt`, `Speedy`), а имената на държавите се вземат от `Intl.DisplayNames` с
  истинския BCP-47 таг от `LOCALE_META.hreflang` (иначе cz/si/gr падаха на английски).
- Админ екран **„Текстове на чекаута“** (`/admin/ui-strings`): избор на език, таблица с ключ +
  български източник + поле за редакция, запис, връщане на оригинала и бутон „AI превод от
  български“ (Claude, пази заместителите). Записаното се пази в `settings.ui.strings` и се налага
  върху вградените текстове през `GET /api/ui-strings` — без ново качване на сайта.
- **Един бутон за всичко:** Админ → Продукти → „Преведи всичко с AI (всички езици)“
  (`POST /api/admin/translate/bulk {resource:"everything"}`) вече включва и текстовете на чекаута —
  `_run_bulk_translate` извиква `ui_strings.translate_locale()` за всеки език и го отчита в прогреса.
- Тестове: `tests/test_ui_strings.py` (парност на ключовете, заместители, нула кирилица в чуждите
  езици) + `tests/test_iteration29_ui_strings.py`; iteration_29 отчет — 100%.
- Остава на собственика: да натисне „Преведи всичко“, за да се преведат и заглавията/описанията на
  продуктите (интерфейсът вече е преведен, продуктовите данни идват от базата).

### Origin сертификати — къде да ги сложиш
1. Cloudflare → зоната (purepeptide.eu / .ro / .gr) → SSL/TLS → Origin Server → Create Certificate.
2. Качи файловете на **pp-front** (frontend сървъра), примерни пътища:
   `/etc/ssl/cloudflare/purepeptide.eu.pem` + `.key`, същото за `.ro` и `.gr` (права 600, root).
3. Попълни ги в `deploy/hetzner/ansible/group_vars/all.yml` под `site_tls_certs:` (примерът е
   закоментиран в `all.yml.example`) и пусни `deploy_nginx.yml`. Домейн без запис ползва общата двойка
   `ssl_cert_path`/`ssl_key_path`. .eu е една зона → един сертификат покрива всички /en /de /fr /cz
   /hu /pl /sk /si префикси.

### 2026-06 — счупените снимки на Ретатрутид (продукция) и управление на медията
Измерена причина, не предположение: пътят на файла беше sha1 на **пълния** Shopify URL, а Shopify
слага `?v=<версия>`, която се сменя при всяка редакция. Повторният импорт е издал НОВИ пътища, а
байтовете са останали под старите → продуктът сочи 404, макар същата снимка да е четима на
продукцията под другия хеш (проверено с curl: старият хеш връща 200).
- `matrixify_import.store_image()`: хешът вече е върху URL-а **без** query, `image_map` се ключова по
  `key` → повторните импорти сочат същия файл.
- Нов `POST /api/admin/media/repair` (+ бутон **Импорт → „Поправи липсващите снимки“**): обхожда
  продукти, колекции, статии, страници и настройки, проверява дали обектът реално се чете и
  пренасочва към работещото копие на същия файл, а ако липсва — го сваля наново от източника.
  Идемпотентен, има `?dry_run=true`. Проверено: счупени продуктова + статийна снимка → `fixed=3`,
  `unresolved=[]`, втори опит `fixed=0`.
- **Снимки по вариант**: в `AdminProductEditPage` всеки вариант има избор от снимките на продукта,
  „Качи нова“ (закача се само за този вариант) и поле за „беше“ цена. `ProductPage.variantGallery`
  вече ги показва първи при избор на вариант.
- **Блог статии в админа** (`/admin/articles`, ново): 19 статии с корица, качване/URL на снимка,
  редакция на заглавие и резюме, превключвател чернова/публикувана. `GET /admin/articles`,
  `PATCH /admin/articles/{handle}` (пише само подадените полета).
- Ретатрутид блог статията **няма Image Src в Shopify експорта** и е чернова в Shopify — затова беше
  без снимка. Сега черновите не се показват в сайта (`/api/articles`, свързаните статии,
  `link-index`, sitemap) и се качва корица от админа.
- `/articles/<несъществуващ>` вече казва „Статията не е намерена“ вместо вечен спинер.
- Тестове: iteration_30 — 13/13 backend, 0 UI бъга.
- **За продукция:** Save to GitHub → deploy → Админ → Импорт → „Поправи липсващите снимки“.

### 2026-06 — качването на снимки и импортът на продукция (purepeptide-labs.bg)
Измерено на продукцията: 10 от 38 продуктови снимки връщат 404 от backend-а (`{"detail":"Файлът не е
намерен"}`), сред тях и трите ръчно качени (`purepeptide/products/…`) и седемте нови Ретатрутид
импортни пътища. Всички работещи са стари пътища от първия импорт. Без SSH няма как да се види
причината, затова кодът вече се самодиагностицира и самолекува:
- `storage.put_object`: дискът е източник на истината; огледалото към managed storage е best-effort и
  вече НЕ проваля качването (преди при паднало огледало снимката оставаше на диска без запис → 502
  за админа / 404 за сайта).
- `GET /api/files/{path}`: ако файлът е на диска, но записът в `files` липсва (възстановена база,
  паднало огледало) → сервира го и пресъздава записа. Истинско 404 вече носи `Cache-Control: no-store`
  (Cloudflare/браузърът кешираха 404 за 4 часа и „поправена“ снимка стоеше счупена).
- Нов `GET /api/admin/media/status` + панел **Импорт → „Диагностика на снимките“ → „Провери снимките“**:
  папка, потребител, записваема ли е (реален пробен запис), кеш, огледало, брой файлове/записи и
  списък на липсващите с причина („НЕ е на диска“ / „без запис“).
- `media/repair` покрива и качените снимки (не само `import/`) и пресъздава липсващи записи.
- Ansible `deploy_backend.yml`: „Own the release“ (chown root) вървеше СЛЕД създаването на
  `.image_cache` и го отнемаше от сервиса; вече е след него + гарантира, че `media_dir` е на сервиса.
- Тестове: `tests/test_storage_resilience.py`, iteration_31 (7/7 backend + UI качване/диагностика).
- **За продукция:** Save to GitHub → `deploy_backend.yml` → Админ → Импорт → „Провери снимките“ (ако
  каже „НЕ е записваема“ → проблемът е права на `/var/lib/purepeptide/media`) → „Поправи липсващите
  снимки“ → Cloudflare Purge Everything.

### 2026-06 — локална валута в имейлите + нощен архив на снимките
- Имейлите за поръчка вече показваха валутата на поръчката (`*_orig`), но **прегледът от админа**
  („Тестов имейл“ с език ro/pl/cz/hu) взимаше последната поръчка и я показваше в нейната валута (EUR).
  Нов `email_templates.localize_order(order, fx)` преизчислява огледалните суми за избрания магазин.
- Имейлът за забравена количка беше винаги в EUR → сега `render_abandoned(..., fx)` конвертира с
  психологическото закръгляне (`nice_price`) като в количката; `abandoned.py` подава курса.
- Форматът е като в количката (Intl, 0 знака): `638 RON`, `1 299 Kč`, `12 990 Ft`, `249 zł`
  (RON вече не е „lei“). Под банковите данни: „Suma de transferat în EUR: €118.00“ на 11 езика.
  Админ имейлът за нова поръчка: локална сума + (€ еквивалент).
- Тестове: `tests/test_email_local_currency.py`; реална RO поръчка през `/api/checkout` → 638 RON.
- **Нощен архив (03:20, pp-back):** `templates/pp-backup.sh.j2` → `/usr/local/sbin/pp-backup`:
  mongodump + `media-<ден>.tar.gz` (цялата `/var/lib/purepeptide/media`) + `backend.env`, проверка на
  архивите, retention `backup_keep_days` (14), `latest-*` линкове, по избор `backup_offsite` (rsync,
  напр. Hetzner Storage Box). `pp-restore <ден>` връща базата И снимките (спира/пуска сервиса, иска
  потвърждение). `tasks/backup.yml` се импортира и от bootstrap, и от `deploy_backend.yml` (таг
  `backup`, `-e run_backup_now=true` за архив веднага); старият cron само с mongodump е заменен.
  Проверено с истински mongodump/tar срещу preview базата (636K + 14M). README: секция „Backups“.

### 2026-06 — локация само при клик + страница „Контакти“
- Чекаут: модалът искаше разрешение за локация още при отваряне и при отказ бутонът „Намери
  най-близките до мен“ не правеше нищо (грешката се гълташе). Сега при отваряне се ползва само вече
  дадено разрешение (`pfDeviceGeo({prompt:false})` никога не отваря диалога, включително на стар
  iOS без Permissions API); диалогът се показва само при клик; при отказ/грешка под бутона излиза
  съобщение (`locateDenied` / `locateFailed`, 11 езика).
- Страница „Контакти“ (`/pages/contact-1` + alias `/pages/contacts`): нов `ContactInfo.jsx` —
  „отговор в рамките на 24 часа“, карта „Важно“ (без медицински консултации), работно време Пон–Пет
  10:00–17:00, имейл contact@purepeptide.bg, плюс форма (вече преведена, не само на български).
  Импортираният от Shopify тънък HTML не се показва за тази страница. 17 нови ключа × 11 езика в
  `checkoutStrings.js` + `ui_strings.py`; `pages_seed.py` носи същия текст като fallback.
- Тестове: iteration_32 (8/8 браузърни сценария).
