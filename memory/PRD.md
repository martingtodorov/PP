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
- Static page bodies exist in bg + en only; other locales fall back to English.

## Backlog
- P0: real Matrixify import of the full catalog (user will supply export + theme)
- P1: Speedy API integration with real credentials; admin payment verification workflow
- P1: per-locale static page editor in admin (currently code-level)
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
- Sections: Табло, Продукти (+ редактор), Поръчки, Клиенти, Импорт, Езици и URL, Изтеглени линкове, Настройки
