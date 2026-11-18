# KMJ Licensing Hub — workflow reference only, modern trust is canonical

**Status:** Source-only secure developer-app lifecycle on a stacked draft branch (18 Nov 2026). Not production released. Legacy AuthSP ZIP is a **user journey reference only**, not code, cryptography, credentials, schema, MySQL import, billing truth, UI theme or authority.

## Non-negotiable trust boundaries

1. **Single authority:** Main Platform PostgreSQL/KSLP. Issuer subscriptions, verified customer entitlements, licenses and device activations are different records; never infer paid rights from a trial key, app registration, or a legacy AuthSP screen.
2. **Private keys server-only:** asymmetric license-signing Ed25519 private keys are never shipped in JavaScript, client SDK, source archives, app downloads or browser props. Public verifier keys have explicit key IDs, audience constraints and independently reviewed rotation/revocation policy. A random opaque bootstrap key is **not** a signed offline license.
3. **Authenticated device:** device generates a separate device private key in the OS-backed secure store where available (TPM-backed preferred, no extra paid dependencies). The server verifies per-session proof of possession over a bound challenge, intended product/audience and device identity; never trust only a HWID or client-provided validity flag.
4. **Bounded offline trust:** signed leases must bind product, intended audience, license/activation, device public-key identity, validity window, sequence and key ID. Verify a documented canonical byte format and the exact Ed25519 signature in each supported SDK. No offline client is genuinely uncrackable; compromised local runtimes can be patched and networkless revocation can only be observed after the allowed offline period.
5. **Server policies:** revocation, entitlement state, seats, plan, subscription expiry, app pause, quota, rate limiting, idempotency and audit are enforced on the server within transactional boundaries. Minimize device metadata and rotate signing keys without sharing issuer secrets.
6. **No destructive licensing enforcement:** expiration or denial must not destroy customer data or disable backups/exports. Never silently grant paid plans, bypass MFA, skip CI audit, or weaken TLS/deployment approval.

## Implemented application lifecycle slice (source only)

- **Rename** changes display name only; product_code remains immutable because existing signed entitlements bind to that code.
- **Pause** can be executed with a valid organization `license.manage` capability plus recent password step-up even if the developer rollout flag is OFF or issuer subscription expired. The server takes an issuer row lock before the product lock and commits the change with a bounded actor/reason/action audit event.
- **Resume** and rename additionally demand a currently active, unexpired issuer subscription and the global rollout flag. Missing/unknown app or state fails closed.
- Delegated trial issuance rechecks active product under the same issuer lock; online bootstrap key resolution already filters by `p.status = active`. Exactly repeated changes do not create redundant audit events.
- **No data loss:** pause does not delete licenses, keys, customer accounts, devices, issuer subscriptions or existing activations, and does not mutate the primary protected deployment.

### Important limitation of this first slice

Pausing a developer app **does not immediately invalidate an already-issued, independently signed offline lease**; the contract must define short signed lease expiry, renewal authorization checks, revocation sequence and client conformance tests. Current `license_audit_events` rows are transactional database records, **not cryptographically tamper-evident append-only WORM records**. Those require a separately reviewed design and key custody. The stacked draft now adds current issuer/product policy checks to direct delegated activation, idempotent activation replay and CloudOS-audience lease signing. The direct activation transaction locks the issuer row to serialize with emergency pause. Exact-head negative tests and device-SDK end-to-end review are still required; do not claim immediate offline revocation or zero-bypass licensing.

## Legacy AuthSP mapping (navigation only)

- `manage-apps.php` → developer app create/list/rename/pause/resume under server RBAC.
- `licenses.php` / `users.php` → governed trial/commercial license and customer/device journeys with issuer and payment truth.
- `manage-accs.php` / `reseller-licenses.php` → scoped owner-reviewed delegated reseller roles, settlement/quota ledgers and audit (still pending).
- `sdk-downloads.php` → **real** signed-verifier SDK releases with cross-language conformance vectors (still pending).
- `billing.php` → verified provider transaction → entitlement → license; never generate commercial keys from unverified payments.

## Release acceptance

- Exact-head secure PHP and TypeScript tests, real PostgreSQL transaction/race and tenant-negative tests; independent verifier cross-language vector and replay/rollback tests.
- Full npm production audit must be green; `GHSA-fc5q-39xc-vjpf` currently blocks the parent PR, tracked by issue #893. Never use `--force`, disable audits or claim an upstream fix that has not been independently validated.
- Authenticated owner/developer/customer browser workflows, isolated backup/decrypt/PG+uploads restore, owner-approved protected staging and production rollout with observed live pointer, tested rollback and verified receipts.
- Source PR #892 and issue #650 remain authoritative for the outstanding complete parity scope; this document does not claim those workflows implemented.
