# Public source, private runtime data

This repository contains application code, public UI/branding assets, and explicitly fictional
test fixtures. It must not contain merchant catalog exports, customer/order records, uploaded
media, private courier snapshots, credentials, database backups, or operational reports.

## Production is the source of truth
- MongoDB, the media disk, private environment files and server backups are not part of Git.
- Catalog fixtures are opt-in: `ENABLE_DEMO_DATA=true` is for a local demo only. The production
  environment template sets it to `false`. Existing catalogs are never replaced by fixtures.
- Routine deployment does not purge data or run catalog/media imports. Imports remain explicit
  administrator actions; do not enable import flags during a normal code update.
- Backend deployment preserves existing courier snapshots and image caches in server-side
  `shared/` directories and links the new release to them. Existing shared files are not replaced.
- Frontend deployment preserves existing hero/preview images in server-side `shared/public-media`
  before swapping builds. Uploaded media continues using the production `MEDIA_ROOT`.
- The privately retained Matrixify workbook stays on the server, outside the source repository.

## Preview contains no real merchant records
- `APP_ENV=privacy-preview` and `ALLOW_MANAGED_STORAGE=false` disable managed-storage access:
  missing local files must not restore historical production images into preview.
- Only fictional catalog examples are permitted; no real orders or customers are seeded.
- Preview analytics recording is disabled, so browsing does not refill the database with visitor
  identifiers. Production analytics behavior is unchanged.
- A fictional customer login is not created by default. It requires explicit demo-only credentials
  and an address in the reserved example.invalid domain; production does not create that account.
- The manual cleanup tool refuses remote MongoDB, clusters/replicas, non-preview configuration,
  mismatched database confirmation and external/symlinked media directories. It is never imported
  by the application or called by deployment. It preserves the configured technical admin.
- Courier data and external service credentials intentionally are not supplied with a fresh clone.
  Tests must use disposable synthetic data, not silently fetch/import production data.

## Before sharing
Run `python backend/scripts/check_repository_privacy.py` for a **current-checkout** guard.
It prints file names and violation categories, never secret values. Reports and credentials for
opt-in live tests are local-only and ignored by Git.

This check does not rewrite or certify historical commits, forks, caches or previous clones.
Removing a file from the current version is not historical erasure. Do not publish an old Git
history containing private data; rotate any actual credentials that were previously exposed.