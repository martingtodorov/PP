# Roadmap

## P0 — verified; owner publication step remains
- Current-checkout and local preview cleanup complete; production was not accessed or changed.
- 75 targeted tests passed; browser/build passed; current publication guard reports 0 findings.
- Backend/frontend deployment preservation check passed with no blockers. Existing production
  MongoDB/config must remain the same; fictional samples are disabled there, not a replacement import.
- Before sharing a new repository, keep only the cleaned current snapshot. Old Git history, forks
  and remote caches are separate;
  the owner reports the old repository is no longer public, but this has not been verified here.

## P1
- Throttle catalog synchronization to avoid external rate limits.
- Repeat SEO/content/link checks on production after a code/config update; never import private
  production data into the public source or this demo to obtain a passing test.

## P2 / on hold
- Offer.validFrom: await real date or a future price-effective-date tracking policy.
- Product reviews; post-delivery review invitations; iOS Safari autofill feedback.
- Efficient bounded processing of startup link/typo repair without silently omitting documents.
- Separately consider existing login lockout and explicit credentialed-CORS policy; do not silently
  expand a data-cleanup request into production authentication changes.
- Future enhancement: run the current-checkout privacy guard before every publication.

## Owner restrictions
- No menu overflow/layout changes.
- No production customer/order/media deletion or reset during deployment.
- No real credentials, catalog exports, snapshots or operational reports in Git.