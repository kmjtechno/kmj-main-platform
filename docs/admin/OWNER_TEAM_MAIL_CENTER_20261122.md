# KMJ TECHNO — Owner & Organization-Team Mail Center
**Status:** source candidate, not automatically deployed or connected to Gmail. 22 November 2026.

## Roadmap and authority review

Authority: `KMJ_TECHNO_MAIN_PLATFORM_MASTER_ROADMAP_BLUEPRINT_V1_0.md` (Phases 2 and 4), `docs/admin/SUPER_ADMIN_CONTROL_CENTER.md`, `docs/adr/ADR-008-identity-access-platform.md`, `docs/operations/ENTERPRISE_MAIL_DELIVERY_ROADMAP_20261121.md`.

- Owner / Super Admin: `is_platform_owner` + verified email + enrolled passkey + recent password confirmation; no password-only privilege.
- Organization team: current `organization_memberships` role (`owner|admin|member`) and verified email, scoped only to the member's own experience. **Organization `admin/member` is NOT KMJ internal employment or global admin.**
- Gmail-style navigation is an interface pattern, not evidence of Gmail OAuth, inbox sync, IMAP/SMTP integration, delegated access, drafts storage or sent receipts.
- The user has connected Gmail to their own ChatGPT account, **not** to the Laravel application, and that connection is not a credential or approval for employee mailbox access.
- Inbound `info@kmjtechno.com` continues through Cloudflare Email Routing to owner Gmail. Outgoing customer/admin/test mail continues through approved KMJ-elite Laravel sendmail -> Postfix direct primary, Brevo fallback. Never swap inbound MX or advertise Gmail SMTP as the production primary.
- No changes to payment, entitlement, license, customer data, DNS, mailbox credentials, or release signing.

## UX shipped in the source branch

Two first-party, role-checked pages, on the same existing premium KMJ dark/graphite/red visual system:
- `/operator/mail`: Platform Owner only, reusable `OwnerModuleShell` navigation. Five owner templates (operations briefing, approval review, security attention, mail delivery health, commerce review).
- `/team/mail`: Verified organization membership only, five team templates (welcome, access update, task, support, security). This is **not** a staff provisioning or internal HR role system.
- Searchable message list, selected branded preview, Gmail-inspired folder navigation, honest "Not connected" Inbox/Sent/Drafts, responsive mobile/desktop layout.
- Existing exact official `/assets/brand/kmj-email-lockup-dark.png`; plain-text + HTML via the actual tested `emails.kmj-transactional` Laravel views. Short one-action copy inspired by Gmail-reviewed onboarding patterns, but original KMJ text.
- No fabricated message count or fake incoming Gmail content; no cross-user mailbox visibility or operator privileges from org membership.

## Safe preview sending

The only mail write added is optional **self-addressed test preview**, with explicit `[TEST PREVIEW]` subject, no action URL, rate limit 2/minute, audit with kind+audience only, and no caller-supplied recipient/from/body/URL. Laravel notification queued after commit. Requires:
1. `KMJ_WORKFORCE_MAIL_PREVIEW_ENABLED=true` explicitly authorized on Elite **after** signed release and live mail transport acceptance. Default is `false`.
2. `RegistrationMailReadiness::canAttemptDelivery()` true; never call this "delivered" without an actual inbox receipt.
3. Current role guard at every request. Owner test must pass PlatformOwnerAccess and password.confirm. Team test requires current org membership and password.confirm.
4. The button is disabled unless the configured test flag and transport check pass; any API bypass also fails server-side.

These templates are **not** attached to fabricated events. Real automated staff invites, task alerts and owner approval emails require authoritative role provisioning, case/workflow events, deduplicated outbox and privacy review. Do not auto-send old tasks, customers or staff.

## Gmail account integration — separate reviewed milestone

Gmail access requires each owner/staff user's explicit Google OAuth consent and user-scoped `gmail.readonly` (or narrower scopes), separate encrypted token storage, refresh/revoke handling, trusted Google app verification where applicable, audit, minimal retention, inbox search pagination, spam/attachment safety, staff tenant authorization, quota and rate limits. Sending requires additional Gmail scope and explicit per-user action. Do not reuse connected ChatGPT Gmail tokens, impersonate users, read personal Gmail in the Laravel backend or share the owner's mailbox with team users. Until a secure independently reviewed OAuth integration exists, the Gmail folder interface shows `Not connected` truthfully.

## Acceptance tests

```bash
cd apps/platform
php artisan test --filter=WorkforceMailCenterTest
php artisan test --filter=BrandedTransactionalSuiteTest
php artisan test --filter=BrandedAuthMailTest
npm run types:check
npm run build
```

CI exact-head, owner + team authorization and cross-audience negative tests, Laravel Pint/PHPStan, and verified migration/rollback and protected Elite release are mandatory. Do not call this live until deployed SHA and owner authenticated browser proof. Do not enable optional preview sends solely because CI is green.

## Next roadmap gates

1. Authoritative KMJ internal staff identity/role registry and invite/accept/revoke flow, separate from customer tenant org members.
2. Audited event-driven owner/staff alerts, deduplication, rate limiting and suppression preferences.
3. Per-user Google OAuth Gmail connector, never a global shared mailbox secret.
4. Real Inbox/Sent/Drafts, threaded search and reply/compose with least privilege, retention and a formal security review.
5. Prove owner Gmail delivery and staff email test individually, with SPF/DKIM/DMARC aligned receipts and transport evidence. No blanket "all inboxes delivered" guarantee.
