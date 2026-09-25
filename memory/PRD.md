# PurePeptide — current engineering handoff

Communication with the owner: Bulgarian. Stack: React/CRA + FastAPI + MongoDB.
The original task replaces a Shopify storefront/admin with multi-language checkout, fulfillment,
content editing and technically correct SEO. Environment URLs/credentials are private configuration.

## Highest-priority owner instruction
The repository will be public. **No real customer/order/catalog records, exports, uploaded files,
caches, secrets, backups or sensitive reports in the current source tree.** Keep only fictional
test fixtures. The owner also authorized deleting real data from the **local preview only**.
**Never delete or overwrite production records/media as part of this cleanup or deployment.**
The owner reports restricting the old repository's visibility. This environment has no Git remote;
neither its visibility nor remote history has been independently checked or altered.

## Current cleanup work (2026-09-24)
- Removed the real catalog/translations from seed code; replaced with clearly fictional samples.
  Catalog seeding is opt-in via ENABLE_DEMO_DATA=true and refuses any existing/partial/imported
  catalog. Production environment template explicitly disables demo seeding.
- Local preview purge verified standalone loopback Mongo, confirmed exact configured DB, explicit
  privacy flags, preview origin and checkout-contained media path. Removed catalog, operational
  records, customer accounts, files and caches. Configured technical admin was preserved unchanged.
  No remote database, remote objects or production files were deleted. No hidden backups created.
- Preview blocks managed object-store access so old media cannot be re-imported. Production's
  existing storage behavior is unchanged. Local technical credentials remain in ignored .env.
- Removed old reports/probes/screenshots and embedded live-account passwords in legacy tests.
  Live-account tests now require private TEST_ADMIN_EMAIL/TEST_ADMIN_PASSWORD and otherwise skip.
- Git ignores runtime datasets/caches/media/reports. `check_repository_privacy.py` is a read-only
  publication guard for current files. It does not certify or erase historical Git objects.
- Production preservation helper adopts server-local courier snapshots, image caches and marketing
  assets into shared directories before rotating releases. Never overwrites existing shared files.
- See DATA_POLICY.md. Current-checkout cleanup is verified; this is not a certificate for old Git
  history or the remotely hosted repository. No remote connection or push was performed.

## Existing functionality to preserve
- Product title is the sole H1. Description H1 is demoted to H2 in React and prerender.
- Temporary API/5xx/network errors never justify noindex. Real removed resources remain 404.
- Published locale handles are shared across API, SSR navigation and HTML sitemap. Rotations
  invalidate SSR cache immediately; in-flight old rendering must not repopulate that cache.
- Shared SSR/React static-page/HTML-sitemap/articles metadata; no client-only description truncation.
- Scientific-literature fills empty content from published articles plus localized editorial text.
  English FAQ uses existing questions/answers and renders them in SSR with metadata/FAQPage schema.
- /collections is included in every locale's XML sitemap. Public /index.html is 301 in production
  Nginx (EU directly to its canonical locale homepage); private raw shell and SPA fallback stay 200.
- **Do not change menu overflow/layout**: the owner explicitly declined that work.
- Normal deploy does not re-seed catalogs, delete alias page records or automatically run Matrixify.

## Source map
- backend/server.py: API, catalog, settings, rotations, startup and database.
- backend/prerender.py + i18n.py: SEO rendering, routing and published handles.
- backend/page_content.py + literature_copy.py: read-only empty-content resolution.
- backend/scripts/purge_preview_data.py: explicit guarded local-only operator action, never startup.
- backend/scripts/preserve_runtime_data.py: server-only deployment file preservation.
- backend/scripts/check_repository_privacy.py: current-checkout artifact/credential guard.
- backend/scripts/check_internal_links.py: read-only domain-aware crawl; --in-process for preview.
- backend/tests/: fixtures must be invented and use disposable databases. Test reports are ignored.

## Follow-up
- Keep the existing production MONGO_URL/DB_NAME when updating. The production environment disables
  fictional catalog seeding; it shows its existing real database. A new empty database does not
  magically acquire production records. This was explicitly explained to the owner.
- Historical commits still need independent handling; no reset/rewrite/push was performed here.
- Optional Offer.validFrom remains unimplemented: real offer start date is unknown. Do not
  substitute a product creation timestamp or today's date merely to silence a warning.
- Deferred: catalog sync throttling, reviews, post-delivery review requests, iOS autofill feedback.
- External fulfillment/email/AI credentials are intentionally absent; do not claim those flows tested.

## Final verification — 2026-09-25
- **75 targeted pytest tests passed**, including loopback/single-host/refusal gates, configured-admin
  preservation, unknown-collection fail-before-write, production runtime-file adoption/no overwrite,
  storage network isolation, optional demo-account/catalog seeding, and prior SEO regressions.
- Testing agent report: local ignored test_reports/iteration_1.json. It initially found a multi-host
  URI guard gap and a resurrected historically tracked XML report. Both were addressed and retested.
  Final JUnit is ignored `test_reports/pytest/privacy_iteration57_final.xml` (do not use the old
  historically tracked pytest_results.xml path for new reports).
- Publication guard: **0 findings for current checkout**; no weakening of tracked-artifact detection.
- Browser BG/EN fictional product pages: single H1, working image and content. Homepage shows only
  the two fictional products. Build passed with existing React hook warnings. Menu/layout unchanged.
- Preview: no customer/order/visitor records, no non-admin users, no historical local media. Only
  configured technical admin plus fictional catalog and public UI page templates remain. Analytics
  collection is disabled in privacy-preview to avoid restoring visitor identifiers after cleanup.
- Production deployment static check: **PASS, no blockers**. Tested helpers preserve server runtime
  files. No production database/file operations or deployment were executed in this environment.
- The testing agent also suggested existing login lockout/CORS hardening. Those are separate
  follow-up recommendations, not verified regressions in this cleanup; no unrelated production
  authentication policy was changed and no comprehensive security audit is claimed.
## Bugfix — 2026-06 (fork)
- Fixed P0: /pages/articles (ArticlesIndexPage) rendered without <Layout>, so the header, menu and
  footer disappeared when clicking "Научни статии" (desktop nav, mobile sliding nav and drawer).
  Page is now wrapped in Layout; inner <main> changed to <div> to avoid nested main. Verified with
  browser: header+footer present, drawer navigation works.

## 2026-06 (fork) — Checkout page, order upsells, 301 toggle
- **Dedicated /checkout route**: the accelerated checkout left PreCheckoutModal and became
  `components/CheckoutFlow.jsx`, rendered by a lazy-loaded `pages/CheckoutPage.jsx` inside Layout.
  Cart drawer and /cart now navigate to /checkout; the terms checkbox lives on the checkout page;
  an empty cart redirects to /cart. The modal is gone.
- **Order upsells + 5-minute grace window**: every order gets `dispatch_at` = created_at + 5 min and
  is only handed to NextLevel by `fulfillment.dispatch_when_due` / `delayed_dispatch_loop` (claimed
  once via `dispatch_claimed_at`). New API: `GET /api/orders/{id}/upsells` (admin-pinned
  `site.upsell_handles` first, then catalogue, excluding what is already in the order) and
  `POST /api/orders/{id}/items` (adds to the same order, recomputes discount/totals, keeps shipping,
  decrements stock, logs inventory; 409 after the window). UI: `components/OrderUpsells.jsx` on the
  thank-you page with a live countdown. Pinned handles editor in Admin -> Settings.
- **301 rotation toggle**: `GET/PUT /api/admin/rotation-policy` (settings key `rotation_policy`);
  new rotations stamp `redirect_mode` latest_301 or none accordingly (history untouched). Switch in
  Admin -> Изтеглени линкове (`rotation-301-toggle`).
- Testing: iteration_59 report — backend 8/8, all targeted frontend flows pass. Known LOW,
  pre-existing console warning: `<span> cannot be a child of <option>`.

## 2026-06 — Titles are the owner's (no deploy may touch them)
- `prerender.brand_title` and `frontend/src/lib/seo.js` publish the stored title byte-for-byte:
  the automatic " - PurePeptide" suffix and the pipe re-spacing are gone (all locales). An empty
  title still falls back to the brand.
- Boot tasks can no longer rewrite a title: `_fix_typos` skips title/seo_title/menu_title/subtitle,
  `resume_translate_jobs` always resumes with overwrite=False, and `restore_headings` only runs when
  RESTORE_BODY_HEADINGS=true.
- Tests updated: tests/test_brand_titles_and_rotation_404.py (new `test_no_boot_task_rewrites_a_title`),
  tests/test_iter52_live_seo.py. Two live tests in that file still need the real catalogue and fail
  in the purged preview (product 21-retatrutide-5-lrp does not exist) — pre-existing.
- Link audit tool added: backend/tools/link_audit.py (crawls /api/seo/prerender). Current result:
  0 dead internal links.
- Pending, awaiting owner: NextLevel 500 -> readable 502 + 4 hardening spots; admin dead-link report.

## 2026-06 — NextLevel errors, dead-link report, contextual links
- **Readable NextLevel errors**: `app.add_exception_handler(nextlevel.NextLevelError)` turns every
  courier failure into 502 with their own message. Hardened the four crashing spots:
  `/nextlevel/test` (list vs paginated answer, bad sender_id), `/nextlevel/preview` (incomplete
  payload), `create_shipment` (API answering a list) and `fulfillment.refresh_order` (order without
  a stored NextLevel number).
- **Dead-link report**: `backend/link_audit.py` crawls the prerendered site in-process;
  `POST/GET /api/admin/link-audit` (job doc in `db.link_audits`, duplicate-run guard). UI card in
  Admin -> Изтеглени линкове (`link-audit-card`, `link-audit-run`, `link-audit-result`). Current
  result: 54 pages, 0 dead links. The standalone CLI tool was removed in favour of this.
- **Contextual internal links**: `backend/autolink.py` links the first mention of each product in an
  article body to the handle that is live right now (max 6 per article, never inside a heading or an
  existing link, hyphenated names not split). Applied at serve time in `get_article` and in
  `prerender._article`, so a rotation can never leave a dead in-copy link. 5-minute alias cache.
- Testing: iteration_60 — backend 18/18, all targeted frontend flows pass, no open issues.
