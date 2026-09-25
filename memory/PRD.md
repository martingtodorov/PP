# PurePeptide — current engineering handoff

Communication with the owner: Bulgarian. Stack: React/CRA + FastAPI + MongoDB.
The original task replaces a Shopify storefront/admin with multi-language checkout, fulfillment,
content editing and technically correct SEO. Environment URLs/credentials are private configuration.

## Highest-priority owner instruction
The repository will be public. **No real customer/order/catalog records, exports, uploaded files,
caches, secrets, backups or sensitive reports in the current source tree.** Keep only fictional
test fixtures. Never delete or overwrite production records/media.

## Existing functionality to preserve
- Product title is the sole H1. Description H1 is demoted to H2 in React and prerender.
- Temporary API/5xx/network errors never justify noindex. Real removed resources remain 404.
- Published locale handles are shared across API, SSR navigation and HTML sitemap. Rotations
  invalidate SSR cache immediately.
- /collections is in every locale's XML sitemap. Public /index.html is 301 in production Nginx.
- **Do not change menu overflow/layout**: the owner explicitly declined that work.
- Normal deploy does not re-seed catalogs, delete alias page records or run Matrixify.
- Titles are the owner's: no brand suffix is ever written into the DB; `prerender.brand_title` and
  `frontend/src/lib/seo.js` publish the stored title byte-for-byte.
- **PUT /api/admin/settings replaces the whole settings document** — always GET, patch, PUT back.

## Source map
- backend/server.py: API, catalog, settings, rotations, robots.txt, startup, database.
- backend/prerender.py + i18n.py: SEO rendering, routing, published handles, private-route noindex.
- backend/autolink.py, backend/link_audit.py: contextual internal links, dead-link report.
- backend/nextlevel.py + fulfillment.py: courier API, 5-minute delayed dispatch.
- frontend/src/lib/ga4.js + components/Analytics.jsx: GA4 pixel (consent-gated).
- backend/scripts/: preview purge, runtime-file preservation, privacy guard, link checks.
- memory/eu_audit.py, memory/eu_crawl.py: read-only live audits of purepeptide.eu.

## 2026-06 (fork) — Checkout page, order upsells, 301 toggle
- Dedicated `/checkout` route (`components/CheckoutFlow.jsx` + `pages/CheckoutPage.jsx`), no modal.
- Order upsells with a 5-minute grace window before NextLevel dispatch (`dispatch_at`).
- 301 rotation toggle in Admin → Изтеглени линкове; dead-link report card.
- NextLevel failures answer 502 with the courier's own message.

## 2026-06-25 — Checkout polish, delivery ETA, order numbers
- Removed the duplicated logo from the checkout page (Layout's header is the only logo).
- Country select narrowed (`.nc2-row2--contact`, 0.72fr/1.28fr) so the phone group gets the width.
- Delivery window on /checkout (`pc-delivery-eta`, key `deliveryEta` in all 11 locales):
  **BG/GR/RO 1–3 working days, every other country 5–8**.
- Order numbers are now **4 letters + 2 digits** (`_next_order_number`, alphabet without I/O).
- Verified: iteration_62 (logo + width), iteration_63 (ETA + order number + tracking regression).

## 2026-06-25 — GA4 pixel
- `lib/ga4.js`: Consent Mode v2 defaults denied, gtag loaded only after the **„Анализ"** cookie
  category is accepted, `send_page_view:false` + one `page_view` per route from `Analytics.jsx`.
- Ecommerce: `view_item` (ProductPage), `add_to_cart` (CartContext.add), `begin_checkout`
  (CheckoutFlow, ref-guarded against StrictMode), `purchase` (thank-you page, once per
  order_number via sessionStorage).
- IDs live in settings: `ga4_measurement_id` (shop-wide) + `ga4_ids` per domain
  (bg/en/gr/ro), editable in Admin → Настройки. Preview holds `ga4_ids.bg = G-2QFH2JXEZS`.
  One ID may serve every domain (split by Hostname in GA4); a per-domain ID is optional.
- Verified: iteration_64 (consent gate, reject path, page_views, all four ecommerce events,
  purchase de-duplication, admin persistence).

## 2026-06-25 — GSC index coverage on purepeptide.eu
- Live audit of all 496 sitemap URLs: 0 broken, 0 noindex, 0 redirects, all self-canonical.
  A 227-page Googlebot crawl found 0 broken and 0 redirecting internal links.
- Fixed „Excluded by noindex" (177): the SSR shell answered `index,follow` for /cart, /checkout,
  /account, /track while React said noindex → `prerender._private_shell` now emits
  `noindex, follow` so crawler HTML and the app agree.
- Fixed „Blocked by robots.txt" (5): robots.txt no longer disallows cart/checkout/account (only
  /admin and /*/admin), so Google can see the noindex and drop those URLs for good.
- Still open, needs the owner's GSC per-URL export (the CSVs he sent are the summary chart only):
  **Not found 404 (474), Page with redirect (72), Crawled – currently not indexed (57),
  Duplicate Google chose different canonical (7), access forbidden 403 (1)**. In GSC: click the
  reason row → the examples table → Export.

## Backlog
- P1: catalog sync throttling (rate-limited external source).
- P1: decide the 404 strategy for the 474 legacy URLs (301 to the closest live handle vs 410).
- P2: product reviews with ratings; post-delivery review request emails.
- P2: iOS Safari autofill feedback.
- LOW: pre-existing console warning `<span> cannot be a child of <option>` (dial-code select).
