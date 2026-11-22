# KMJ Licensing Hub — customer-safe KSLP parity slice (22 Nov 2026)

**Status: source PR only. Not installed, deployed, commercial-ready or complete AuthSP parity.**

KMJ TECHNO has **one** Laravel/PostgreSQL/KSLP commercial licensing authority.
The prior AuthSP archive is a user-workflow reference only. Never import its
historical user DB, sessions, OAuth state, issuer signing keys, auth, billing
credentials, SQL or insecure server-side PHP into KMJ production.

## One-account journeys

- **Super Admin:** `/operator/kslp` remains the only global owner
  Licensing Hub. Owner passkey, verified account and recent password
  confirmation apply to protected mutations; customer users cannot access it.
  Existing license issue/revoke/renew/plan changes retain their gates.
- **Developer:** `/developer/apps` remains an organization-scoped view
  of the same KSLP tables. Active issuer entitlement, organization
  `license.manage`, feature rollout gate and step-up protect issuance.
  Trial bootstrap keys are not production signed commercial leases.
- **Customer:** `/licensing` is the nonowner default **Licensing Hub** sidebar
  entry, under the existing authenticated + email-verified web group.
  Same account/membership scope serves **My Products → Licenses → Devices
  → Downloads**, without a second database or login. Licenses show safe
  plan, status, expiration and aggregate device binding counts. A
  non-deactivated binding is **not evidence the device is online**. Signed
  license issuance cannot be inferred from an organization entitlement.
  Downloads link to the pre-existing entitlement-aware account dashboard;
  this route never invents a signed binary download URL.
- **Reseller:** still **not production-ready**. No reseller issuance,
  quota, credit balance, purchases or delegated grants are manufactured.
  Must implement real server-side reseller grants/ledger and customer
  settlement before exposing a new privileged console.

## Fail-closed customer privacy and safety

- KSLP license lookup is restricted to the authenticated user ID plus
  organization IDs returned by the existing authoritative
  `OrganizationDirectory::forUser()` scope. No query string supplies
  arbitrary customer/organization IDs. Output is bounded to 100 rows.
- Entitlements are queried only for the same verified memberships.
- Activation history uses aggregate counts and latest date **only**.
  Never render device public keys, hardware hashes, identity strings,
  raw tokens, KSLP bearer secrets or idempotency keys.
- Customer route sets `Cache-Control: private, no-store`.
- No customer reset/transfer POST has been introduced. Device recovery
  requires possession proof, cooldown, current revocation sequence and a
  reviewed authorization policy; UI states blocked rather than a fake
  action. Paid issuance likewise requires actual settlement → entitlement
  transaction proof.
- Owner navigation remains anchored to the existing global
  `/operator/kslp`; customer sidebar uses one `/licensing` entry, with
  a link to the existing developer section rather than another admin hub.

## Required next development gates (not waived)

1. Workable, auditable customer device release/transfer with exact
   org membership + receipt-bound challenge, revocation sequence and
   cooldown, plus concurrent/replay negative tests.
2. Reseller delegated per-product role, quota/credit immutable ledger,
   staff restrictions and cross-tenant denial. No fabricated balances.
3. Payment provider webhook order settlement → subscription → entitlement
   → product-scoped signed license, idempotent and reconciled with refund.
4. Real signed C#/.NET, C++/Qt and Rust verifiers, release digest and
   offline revocation/clock rollback conformance, not merely snippets.
5. Complete issuer app settings, bulk dry-run/import/export and bounded
   key lifecycle with owner step-up, no plaintext key persistence.
6. Verify protected Elite staging, isolated PostgreSQL+uploads restore,
   rollback, owner authenticated browser acceptance and an exact-head
   independently approved signed release before production activation.

No deletion of email-unverified accounts was authorized by this slice.
The existing owner-only cleanup remains disabled pending cohort preview,
backup/recovery witness, explicit owner confirmation and protected gates.
