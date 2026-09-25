# Private configuration (names only)

Keep real values exclusively in private environment files or production settings. Do not copy them
into chat, repository examples, reports, tests, seed data or frontend bundles.

- Database: MONGO_URL, DB_NAME. Protected existing names/values are not changed by cleanup.
- Authentication: JWT_SECRET, ADMIN_EMAIL, ADMIN_PASSWORD. Preview's technical admin is preserved.
- Email: RESEND_API_KEY and private sender configuration.
- AI: ANTHROPIC_API_KEY / EMERGENT_LLM_KEY.
- Shipping: NextLevel credentials and any settings-stored integration credentials.
- Push: VAPID_PRIVATE_KEY and associated configuration.
- Bank/company details: runtime settings/environment only.

Production configuration and data are outside Git and are not reset by a routine deployment.
Privacy preview disables remote managed storage and contains fictional fixtures only. Services
without private credentials/data are not expected to work there; do not replace them with an
undisclosed mock or fetch production data automatically.

Use separate private TEST_ADMIN_EMAIL and TEST_ADMIN_PASSWORD only when explicitly running
authorized live-account tests. Do not publish their values. Rotate any actual credentials that
were exposed in prior public commits; rewriting current files does not revoke a credential.