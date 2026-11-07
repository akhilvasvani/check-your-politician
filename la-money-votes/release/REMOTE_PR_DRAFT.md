Integrates the existing transcript branch with current main and prepares the weekend release for review. Transcript search now preserves independently successful official/public-comment results, validates inputs and server-owned official identity, and uses bounded requests with durable aggregate limits. Finance, public-action and transcript disclosures explain source coverage and uncertainty.

This remains a draft. The source inventory, offline evaluation, replacement safeguards, API/UI regressions and operations evidence are documented in `la-money-votes/release/RELEASE_PACKET.md`, `OPERATIONS.md` and `source-status.md`. The source SHA proposed for remote validation is `<APPROVED_RELEASE_SHA>`; bind it in the approval record after preparation commits are final.

Local validation includes offline Python/Node suites, disposable PostgreSQL/pgvector tests, schema/build checks and desktop/mobile browser checks. The release packet records exact counts and limitations. GitHub CI and Vercel preview verification for this PR are pending. The CI PostgreSQL step intentionally collects and skips database integration tests; that job is not evidence of live database behavior.

Public release gates remain open, including verified caption material, independent speaker review, live relevance evaluation, browser-role privilege hardening, approved replacement-RPC migration, deployment credential/limiter verification and exact-SHA preview review. No paid API batch, shared data write, merge, production deployment or promotion is authorized by this draft PR.

The reviewed push/PR approval must account for automatic Vercel preview side effects. See `la-money-votes/release/REMOTE_VALIDATION_PLAN.md` for the inspected configuration, unresolved Git settings, proposed actions and recovery steps.
