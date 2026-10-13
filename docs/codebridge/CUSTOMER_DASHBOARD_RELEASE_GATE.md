# CodeBridge Customer Control Center — Release Acceptance

This is a **release gate**, not a declaration that the customer dashboard is deployed or production ready. Preserve the existing KMJ TECHNO branding and use no paid dependencies.

## Source integration and approvals

Merge the reviewed, dependency-ordered pull requests; never merge stacked children directly into main:

1. Main Platform PR #379: audited Device Control Center and honest device-registration language (supersedes #377/#378).
2. PR #381: modular hub, licensing/usage/billing/security summaries; branch based on #379.
3. PR #382: Gemini Spark OAuth opaque-state handling; branch based on #381.
4. PR #386: real accessible panel selection, mobile navigation, readable labels, tests and production frontend build; branch based on #382.

Before each merge, fetch the *current* head, verify ancestry and mergeability, check required review approvals and complete exact-head CI evidence. Do not silently skip absent or unexecuted GitHub Actions; their setup/billing investigation is Issue #361.

## CI in a disposable checkout

- Run **all** frontend format/lint contracts (`npm run check`) and TypeScript (`npm run types:check`). Reconcile any baseline failure before release; CircleCI's focused device job is not a replacement for the full check.
- Run the existing targeted no-network device-control verifier, which exercises tenant-safe PHP tests and dashboard truth-contract assertions.
- Run `npm run build`, PHP syntax, Pint, PHPStan and the full relevant Laravel feature suite, particularly CodeBridgeAdminHttpTest, CodeBridgeDeviceEnrollmentTest and CodeBridgeOAuthServerTest.
- Run security/secret checks applicable to the repository; inspect the changed files and dependencies.
- Run a clean mobile/accessibility check in staging at 320px, 375px, 768px and desktop; verify keyboard focus, section selection and no clipping.
- Report job IDs, commit SHAs, status, skipped checks and exact scope tested. A baseline-main PASS does not validate a PR head.

## Authenticated customer acceptance

- **Overview:** show only actual tenant-backed license, managed-device count, pending pairing count and OAuth refresh grants. Never describe registration as an online heartbeat, or grants as live IDE sessions.
- **Devices:** search and project filters, bounded lists, details and Copy ID; tenant A must not see or revoke tenant B. Revocation needs organization-management permission, current password confirmation and the exact typed device ID; retry is audited and idempotent. Re-enrollment requires fresh pairing.
- **Setup:** verify VS Code/Copilot, ChatGPT Desktop, Claude and Linux/VPS actions still lead to their real authorized flow; safely handle missing clipboard permissions; never show raw tokens.
- **Connected apps:** search, duplicate names distinguished by client-ID suffix, limited initial cards, revoke confirmation and truthful access-token expiry caveat.
- **Usage and billing:** only show authoritative metering/plan data; label unavailable figures as not reported. Never invent uptime, revenue, invoices, free usage or throughput.
- **Accessibility:** active section is operable by keyboard, section content is discoverable, readable sizes avoid sub-12px labels, no full-page horizontal overflow or mobile navigation trap.

## Staging and production

1. Use a trusted and current backup of the production database, assets/config and application release manifest, and prepare a tested rollback path.
2. Stage exact merged SHA; build assets from that SHA, run migrations only if independently necessary and validated.
3. On staging, run the authenticated customer acceptance matrix and screenshot comparison against the prior dashboard.
4. Deploy only after full gates, review and rollout approval. Verify the **actual** customer-domain deployed SHA and authenticated request behavior, not just repository CI.
5. Check real CodeBridge client and agent health after rollout; the Main Platform dashboard must not infer agent presence from enrollment records. Record the final SHA, acceptance evidence, rollback and unresolved blockers.

Do not modify DNS, OAuth credentials, owner payment settings, P720 dirty files or current gateway runtime as a side effect of this dashboard UI release.

## Known blockers (snapshot, 13 October 2026)

- Original main-platform GitHub Actions jobs fail before executing steps (Issue #361). Do not count these as successful or verified source tests.
- Full `npm run check` was observed failing on the unmodified PR #382 integration source in a disposable CircleCI diagnostic. Identify and fix the exact formatter/lint or environment reason; do not attribute it to PR #386 without evidence.
- Dashboard stacked PRs and deployed source have not been reviewed/merged/accepted in production.
- CodeBridge gateway cutover and source revision are a separate release lane; see CodeBridge Issue #295 and the guarded controller review in PR #341.
