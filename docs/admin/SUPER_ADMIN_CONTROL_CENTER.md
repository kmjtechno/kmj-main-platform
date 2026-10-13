# KMJ TECHNO — Modular Super Admin Control Center

## Goal

A fast, owner-only control surface for all KMJ TECHNO operations, without exposing
customers to privileged actions or requiring new paid services. Modules share one
discoverable navigation design and are backed by explicit server authorization.

## Implemented in this slice

| Area | Entry | Owner workflow |
| --- | --- | --- |
| Platform overview | `/operator` | Verified metrics, users/org totals, entitlements and commercial order status |
| Product manager | `/operator#product-manager` | Create/edit/reorder catalog, lifecycle, visibility, licensing controls |
| Orders & fulfillment | `/operator#commercial-orders` | Governed order review and explicit manual licensed fulfillment |
| Gateway settings | `/operator/payments` | Cashfree/Razorpay sandbox credentials, write-only rotation/revocation, onboarding notes |
| Licensing | `/operator/kslp` | Existing KSLP authorization and audit controls |
| CodeBridge | `/operator/codebridge/owner-plan` | Existing internal license/owner-plan controls |
| Operations | `/operator/ops` | Existing diagnostics, health, backup and governed controls |
| Security | `/settings/security` | Existing passkeys and account security |

User-facing panels share accessible keyboard-friendly responsive navigation.
The legacy monolithic Product Manager has been extracted into a reusable component.

## Payment settings security invariants

- Authentication, verified email, passkey-backed `PlatformOwnerAccess`,
  recent `password.confirm`, CSRF, and rate limiting guard each write.
- Sandbox-only: neither the form nor the server accepts `environment=live`;
  Razorpay live key IDs are explicitly rejected.
- Credentials are encrypted with the Laravel application key at rest and
  are NEVER returned to browser props, success messages, or audit metadata.
  Validation errors exclude the credential fields from flashed session input.
- Only stored/not-stored booleans and descriptive non-authoritative merchant
  statuses are shown to the owner. Approval reported by an owner is **not**
  presented as verified merchant approval.
- Blank credential fields retain existing ciphertext; explicit revoke clears
  the stored keys without revealing them.
- Merchant international **requested** status is a note, not processor approval.
- The payment readiness service reports stored sandbox configuration only;
  live charging stays FALSE and no checkout/charge/webhook endpoint is created.
- Audit records log actor, provider, action and changed **field names only**.
- Provider sandbox keys still require the external merchant dashboard, API
  sandbox tests, signature verification, server-originated order reconciliation,
  refund/dispute workflows and owner-approved live canary BEFORE actual billing.

## Verification / release sequence

1. Build and test against an **isolated** dev copy of the exact PR head.
2. Check PHPUnit owner-authorization, encryption, secret redaction, revocation,
   audit logging, denial of live keys, and validation failures.
3. PHPStan + Laravel Pint; Wayfinder-generated typed routes, TypeScript and
   frontend lint; Vite build; product/order/license regression tests.
4. Create a backup and test the migration on staging PostgreSQL before production.
5. Require exact-head hosted CI (or approved independent equivalent). If GitHub
   Actions is blocked by account billing/runner restrictions, keep the PR open.
6. Review key-rotation procedures and rollback; perform controlled deployment
   only when code, migration, permissions and owner acceptance all pass.

## Additional modules planned (NOT claimed complete)

1. Users and organizations: searchable lists, role changes with passkey
   re-authentication, explicit invitations, scoped permissions and audit.
2. Products and licenses: independent catalog, pricing/plan versioning,
   product releases, entitlement lifecycle and delivery.
3. Finance: sandbox-to-live merchant verification, multi-gateway checkout,
   invoices, refunds, reconciliation and international tax/currency settings.
4. Operations: deployments, backups, incident timeline, connection health,
   secure one-click actions with immutable rollback and approval gates.
5. Communications: support desk, customer email templates, notices and
   opt-in notifications with user-consent and deliverability checks.
6. AI/automation: zero-paid-cost model routing, ModelFabric and Kristi
   execution controls with daily quotas, kill switches and audit logs.
7. Reporting: reliable revenue and customer analytics with cost and data
   provenance, export and privacy controls.

The first release does not claim that all these future modules exist. Feature
status in Super Admin must always reflect verified backend capability.

**Cost policy:** reuse the current KMJ VPS, CodeBridge and free-tier tooling;
no automatic paid upgrades or paid AI provider fallbacks. Payment processors
may still charge transaction fees if live commerce is later activated.
