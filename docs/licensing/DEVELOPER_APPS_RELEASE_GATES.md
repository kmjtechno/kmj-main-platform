# KMJ Developer Apps — AuthSP-inspired licensing workflow

Status: **Stacked development PR, not a production release** (2026-10-12).

## User experience (corrects confusing /sandbox-licenses screenshot)

1. Sign in and open **Developer Apps & Keys** in the platform sidebar or dashboard.
2. Create an organization if none exists. This does **not** create a paid issuer subscription.
3. Once owner-approved KSLP issuer subscription is active, register an application with a unique uppercase product ID. Stored in existing `kslp_licensed_products`, with tenant limit enforcement.
4. Select app and customer reference. **Only a 30-day trial key is currently permitted by the new self-service service and HTTP route.** A developer issuer subscription is not proof of a customer's paid purchase. Professional, business, enterprise and OEM keys remain blocked until verified payment/entitlement reconciliation and approval. Generate an opaque 256-bit trial bootstrap key via existing delegated KSLP quotas. Persist only SHA-256 key digest, never plaintext; display full key in the authorized step-up flow.
5. On first launch (staging only), client generates Ed25519 keypair and random per-installation ID. It sends the bootstrap key and **public** device identity to `POST /api/v1/kslp/developer/activation/challenge`. The server returns challenge ID and nonce.
6. Client signs `KSLP-ACTIVATE-v1|<license_id>|<nonce>` with its private device key and submits signature and SHA-256 installation hash to `POST /api/v1/kslp/developer/activation/complete`. Server verifies key, existing license/issuer/product, challenge lifetime and proof, and records activation once. Optional platform/app version stored **only** if `metadata_consent=true`; raw MAC, serial, CPU IDs and hardware fingerprints are never requested.
7. Staging API returns `signed_lease_issued=false`. **This is device registration, NOT a usable signed commercial product license.** Production client SDKs and per-product signed entitlement leases are not enabled until explicit release gates.
8. Language selector supports starter **configuration instructions** for TypeScript, Python, C#/.NET, C++/Qt, Rust, Go, Java and PHP. These are not yet downloadable, audited, working production SDK libraries.
9. The old `/sandbox-licenses` route remains the separate **Sandbox Token Lab**, which issues short-lived testing tokens and is not advertised as customer licensing.

- **Paid-plan safety:** `KslpDeveloperKeys::issue()` rejects non-trial plans with `KSLP_PAID_ENTITLEMENT_REQUIRED`; HTTP issuance accepts only `trial`. Future paid issuance must require recorded provider settlement and a transactionally verified entitlement before any key is created. No self-service subscription is sufficient.
- **Consent withdrawal:** activation and consented metadata commit together; retry with `metadata_consent=false` removes previously stored optional platform/app version and consent timestamp.

## Trust and security boundaries

- KMJ Main Platform/KSLP alone issues commercial rights; no AuthSP PHP/MySQL app or its secrets are imported.
- App creation and key issue require verified sign-in, `license.manage` in matching organization, active issuer subscription, and recent password confirmation. Explicit rate limits.
- Issuance defaults **OFF** via `KMJ_DEVELOPER_LICENSING_ENABLED=false`; enable only on isolated staging after migration and tests.
- Key is a high-entropy **bearer bootstrap credential**, not a client-verifiable license or permanent entitlement. Rate limiting limits guessing; protect key at rest on clients and rotate/revoke compromised keys. Revocation and quotas must be reverified before any renewal.
- One active device seat currently enforced by KSLP. A stolen unused key could be activated first by an attacker; device key proof alone does not prevent theft of an unused bootstrap credential. Future anti-abuse includes owner step-up, expiring claim links, recipient verification, device limits, anomaly rate limits and customer self-service recovery.
- Security cannot guarantee that software is impossible to crack. Use signed short-lived leases, server-authoritative entitlements, device proof and cryptographically verified releases to make tampering more difficult and limit damage.
- No private signing key in products or frontend, and no customer data destruction when restricted.

## Files introduced

- `apps/platform/database/migrations/2026_10_12_120000_create_kslp_license_keys_table.php` — minimal key identity + opt-in metadata.
- `apps/platform/app/Services/Licensing/Kslp/KslpDeveloperKeys.php` — hash-only key issue/resolve with issuer and license checks.
- `apps/platform/routes/developer-licenses.php` — protected app registration, key issuance, tenant-filtered dashboard, organization onboarding.
- `apps/platform/routes/developer-activation-api.php` — staging-only challenge/proof registration in API middleware.
- `apps/platform/resources/js/pages/developer-apps.tsx` — cohesive app/key/SDK setup dashboard.
- Feature tests: `KslpDeveloperAppsTest.php` and `KslpDeveloperActivationApiTest.php`.

## Release gates (all required before enabling flag)

- [ ] Stacked prerequisite security PR #371 exact-head PHPUnit/Pint/PHPStan and approved CI GREEN.
- [ ] This PR exact-head PHP formatting, static analysis, TypeScript, Vite, Laravel feature tests, Rust KSLP golden interoperability GREEN.
- [ ] Isolated PostgreSQL migration and rollback including production-compatible schema and no lost legacy keys.
- [ ] First-login abuse testing: forged proof, expired challenge, replay, cross-tenant collision, quota, rate limits, revocation, first-use key theft and account recovery.
- [ ] Authenticated activation privacy/consent tests, duplicate requests, actual no-secret-log verification; secure first-run client key and checkpoint storage.
- [ ] Genuine language-specific SDK packages, positive/negative conformance vectors and per-language runnable samples; do not pass generic setup manifests off as SDK implementations.
- [ ] Per-product audience/version interoperability beyond CloudOS KSLP-v1; versioned signed leases and production KMS signing-key custody/rotation. Current activation API intentionally returns no signed lease.
- [ ] Payment settlement -> entitlement authority -> license issuance reconciled (Cashfree/Razorpay separately owner approved), no activation solely from unverified payment status.
- [ ] Accessible mobile/desktop testing, proper tenant and support views; backup, rollback and release acceptance; required CI restored. No paid subscription or bypass.
- [ ] Only then stage canary -> production enable with monitored rollback and owner acceptance.

**Important:** The existence of this staged implementation does not mean KMJ's licensing is production-ready.
