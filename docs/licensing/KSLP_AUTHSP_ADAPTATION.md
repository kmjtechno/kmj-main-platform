# KMJ Licensing — safe AuthSP feature adoption

Status: **implementation slice 1; staging only** (2026-10-12). This change does **not** enable production signing, live payments, migrations, new endpoints or customer-facing SDKs.

## Architecture decision

- **Single authority:** KMJ Main Platform + KSLP, not the AuthSP PHP/MySQL server. Do not import its production-shaped sessions, OAuth state, caches, keys, checkout, or database SQL.
- **Keep KSLP-v1 CloudOS compatibility:** existing Ed25519-only signed leases, canonical golden vectors and fail-closed parser are unchanged.
- **Adapt AuthSP ideas, not source:** typed multi-language clients, offline usability, device reset/transfer UX, reseller administration, public key caching and diagnostics.
- Reuse existing KSLP issue/renew/revoke/reactivate/transfer, activation proof, signing key registry, delegated issuer quotas and audit instead of introducing another source of truth.

## Slice 1: opt-in CloudOS offline validation policy

`KslpOfflineLeaseGuard::verify(...)` wraps the existing `KslpVerifier` and adds consumer-side constraints:

1. Require only authenticated **license-purpose** Ed25519 public keys. A token-provided key is not a trust root; never place private keys in client binaries.
2. Bind signed lease to the **exact** server identity, activation ID and license ID from previously verified online activation.
3. Bound the signed offline window to **24 hours** from issuance, with no extension past the signed commercial `grace_until` ceiling. Actual server-issued leases may be shorter.
4. Deny clock rollback beyond 5 seconds relative to a trusted checkpoint; deny missing checkpoints and stale sequence numbers. A known revocation always denies, including within grace.
5. Verify claims in memory only; no writes, remote calls, activation, checkout, or entitlement grants. Fail closed with existing v1 error codes.

**Important limitations:** trustworthy `lastTrustedUnixTime` and `minimumSequence` require a secure platform/client storage implementation, not caller-supplied user input. Offline revocation is inherently delayed until reconnect or lease expiry. On compromised client hardware these checks are not absolute anti-tamper controls.

**Compatibility:** `KslpVerifier` currently accepts `aud=kmj-cloudos` only; this offline guard is deliberately **CloudOS-only**. Do not silently reinterpret KSLP-v1 to support OmniDesk, CineCore or other audiences; add separately versioned product profiles, interoperability vectors and per-device tests first.

## SDK integration plan

- **First activation online:** generate a device keypair locally, prove possession, obtain server-authoritative signed entitlement and bind activation.
- **Cache signed bytes** in OS-protected storage (DPAPI/TPM on Windows, Keychain on macOS, Secret Service/TPM where available on Linux); locally encrypted random session IDs are not license evidence.
- **Offline use:** verify Ed25519 signature against pinned license key, audience, product, exact activation and license, time, anti-rollback checkpoint and minimum sequence. Denied licensing must not destroy websites, databases, backups or recovery/export access.
- **Reconnect:** verify current server activation, revocation, merchant-linked entitlements and signing key status; rotate/reissue leases. Use bounded exponential backoff; no repeated origin calls while offline.
- **Client interop:** initial C++/Qt and C# SDKs, then Rust/Go/Python; cross-language golden positive and negative vectors for wrong device, revoked key, stale seq, rollback, future issue and expiry.

## Activation replay hardening (same draft PR)

The existing KSLP control plane previously returned the first activation matching an idempotency key without checking the original license, Ed25519 device identity or hardware identity. That could disclose a different license's activation record or revive a deactivated activation.

This development slice now performs an exact license + server identity + machine hash comparison on **both** idempotency paths, rejects deactivated records and known license revocation, and rejects a changed machine hash on the existing active-device path. The original same-device retry remains supported without repeating owner pairing. Hardware changes require a separately approved transfer, not a silent refresh.

Regression coverage added to `KslpLifecycleTest`: cross-customer idempotency collision, device and HWID mismatch, valid possession proof with changed HWID, old retry after transfer, retry after revocation. These are **authored tests, not yet executed via Laravel's real PostgreSQL/PHPUnit environment**. An isolated crypto harness covers the offline-only class but does **not** prove DB transaction behavior. Release stays blocked until exact-head feature tests and transaction/race checks pass.

## Super Admin module roadmap

One consistent Licensing experience: searchable product/customer/license directory, actual active/trial/renewal due/grace/restricted/revoked states, device seats, expiring-soon queue, signed issuance and renewal, safeguarded device reset/transfer, delegated reseller quotas, immutable audit and support-level read-only workflows. High-risk actions require owner step-up, explicit reason, tenant-scoped authorization and confirmation. Merchant payments must settle and reconcile **before** entitlement issuance; no live checkout is enabled by this slice.

## Cost and operational design

One PostgreSQL authority, existing queue/scheduler, optional bounded Redis for rate limits, CDN cache for **public keys only**. Do not run AuthSP's unauthenticated WebSocket broadcaster or a second paid server. Clients validate offline in-process without VPS round-trips.

## Production release checklist (not yet fulfilled)

- Exact PR head formatter, PHPUnit, PHPStan/Pint and compatibility golden tests PASS.
- C++/C# clients implement secure checkpoints and verify the same negative vectors.
- Tested key rotation/revocation and device transfer; no secrets in logs or browser responses.
- Isolated staging/rollback for any future schema changes, production backup, owner acceptance and signed release gate checks.
- Do not merge or deploy merely because an isolated smoke test passed; GitHub Actions runner/billing blocker #361 remains separately tracked.

AuthSP archive was only examined as design reference; no source code or runtime state from it is vendored into this PR.
