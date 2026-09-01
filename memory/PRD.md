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
