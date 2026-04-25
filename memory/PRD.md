# PurePeptide — Product Requirements Document

## Original problem statement
Build a custom storefront + admin backend to replace the Shopify store at purepeptide.bg using React + FastAPI + MongoDB. Bulgarian-language peptide e-commerce with bank-transfer checkout, manual payment verification, and Speedy/Econt shipping integration.

## Stack
- Frontend: React 19 (CRA + craco) + Tailwind + shadcn/ui + Manrope/IBM Plex Sans
- Backend: FastAPI + Motor (async MongoDB) + JWT (httpOnly cookie `pp_token`) + bcrypt
- DB: MongoDB (UUID-string IDs, _id excluded from responses)

## User personas
1. **Customer (BG)** — browses Bulgarian catalog, adds peptides to cart, places bank-transfer order with Econt/Speedy shipping
2. **Admin** — verifies bank-transfer payments, creates shipments, manages catalog, imports CSV

## What's been implemented (2026-04-25)
### Backend
- JWT auth (register/login/logout/me) with httpOnly cookies; bcrypt; role-based (admin/customer)
- Public: collections, products, articles, settings
- Checkout: validates stock, decrements inventory, returns IBAN/BIC/reference, supports guest + auth user
- Customer order history: `/api/me/orders`
- Admin: stats dashboard, orders workflow (mark-paid, mocked Speedy/Econt shipment with tracking number), customers, products CRUD, settings update, Matrixify CSV import (multi-variant grouping, insert/update by handle)
- Seed: 7 collections, 20 peptide products, 4 articles, default site settings, admin + test customer users

### Frontend
- Bulgarian Cyrillic UI, EUR primary + BGN secondary (1 EUR = 1.95583 BGN peg)
- Storefront pages: Home (custom Liquid-derived hero with blurred lab background, infinite logo marquee, USP strip, category grid, best-sellers, peptide concentration calculator, scientific articles, FAQ accordion), Collection, Product (variant selector, gallery, related), Cart, Checkout, Order Success (bank transfer details + copy-to-clipboard), Account (login/register tabs + order history)
- Admin pages: Login, Dashboard (7 stat cards + recent orders), Orders (filter tabs + details modal + mark-paid + create-shipment), Products, Customers, CSV Import (drag-drop UI + history), Settings
- Cart: localStorage-persisted (hydration-safe), drawer with EUR/BGN, badge in header

### Design
- Manrope display + IBM Plex Sans body, blue-600 primary, Swiss/clinical 1px borders
- Custom hero per user-supplied Liquid template (dark background, blur, desktop translateX shift, coral primary CTA + glass secondary)
- Logo marquee strip with 7 brand logos, infinite CSS-only animation

## Tested (iteration 1)
- 40/41 backend pytest tests pass (only failure: `/api/` 404 — non-issue)
- Frontend home + product + add-to-cart manually verified

## Known limitations / Backlog
- **P1** Speedy/Econt shipping is **MOCKED** (generates fake tracking numbers tagged `tracking.mocked: true`). Replace with real Speedy API integration when credentials provided.
- **P1** No email notifications on order placed / payment confirmed / shipped. (Add Resend or SendGrid.)
- **P2** Guest order lookup uses raw UUID (anyone with URL sees PII). Add order-token.
- **P2** Server.py is single file (~750 lines). Could split into routers per module.
- **P2** No real Matrixify import yet — user to upload their `.xlsx` workbook (need conversion to CSV) or extract `Sheet 1` programmatically.
- **P2** No multilingual storefront (Bulgarian only). Add EN locale switcher.
- **P3** No invoice/PDF generation. No product reviews/bundles/upsells.
- **P3** No SEO redirects table populated yet (collection exists in MongoDB).

## Next tasks
1. Real Speedy API integration (request creds from user)
2. Email notifications via Resend
3. Upload + parse the user's actual Shopify theme archive + Matrixify export to migrate live data
4. SEO redirects from old Shopify URLs to new handles

## Test credentials
See `/app/memory/test_credentials.md`.
