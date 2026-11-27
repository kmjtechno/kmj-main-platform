# OmniDesk M9 protected issuer: verified state, design and blocker register

Status: **design and blocker register only. No issuance is enabled by this document.**
Date: 2026-11-03. Evidence: source on `main` at `e8b5fce8`. Nothing here was deployed or run on a host.

## 1. Verified current state (from source)

| Endpoint | Behaviour on `main` |
| --- | --- |
| `POST /api/v1/licensing/omnidesk/activations` | Authenticates, requires `canManage`, then always returns `503 ISSUANCE_NOT_CONFIGURED`. Body cap 2048 B, `throttle:12,1`. |
| `POST /api/v1/licensing/omnidesk/leases/renew` | Same fail-closed 503 stub. |
| `GET  .../activations/{id}/status` | Implemented (`OmniDeskActivationQueryService::status`), tenant-scoped. |
| `GET  .../entitlements/current` | Implemented. |
| `POST .../activations/{id}/renewal-challenge` | Implemented, owner-managed only (`OmniDeskRenewalChallengeStore::issue`). |
| `POST .../activations/{id}/deactivate` | Implemented with mandatory reason. |

Existing building blocks (all present and unit-tested, none wired to a signer):

- `OmniDeskActivationProof` / `OmniDeskRenewalProof`: Ed25519 device-possession proofs with length-prefixed canonical messages and a domain tag.
- `OmniDeskActivationBindingStore::bind` and `::advanceLease`: transactional, lock order license -> activation -> entitlement -> binding, exact-match idempotency, replay cursor (`current_jti`, `current_sequence`, `current_nonce`).
- `OmniDeskRenewalChallengeStore`: single-use server challenge, tenant bound.
- `OmniDeskEntitlementIssuer::issue(claims, OmniDeskSigner)`: validates every required claim and returns a detached-signature envelope. It never sees key material.
- `OmniDeskSigner` interface: `kid()` and `sign()` returning a raw 64-byte Ed25519 signature; documented as KMS/HSM-delegating.
- `OmniDeskApiAuthorizer` interface: **no concrete implementation is bound**. Without a binding every call to the routes above fails closed with `SERVER_UNAVAILABLE` (503).

Not present anywhere in the repository (searched `app/`, `config/`, `docs/`):

1. A plan -> {capabilities, limits, lease TTL, grace} mapping. The issuer requires `licensed_users`, `managed_devices`, `concurrent_sessions`, `unattended_devices`, `relay_bytes_monthly` and `relay_policy`, but no source defines their values per plan.
2. A concrete `OmniDeskApiAuthorizer` (how a tenant or device principal authenticates).
3. A concrete `OmniDeskSigner` backed by KMS/HSM, and a published verification key set behind `GET /api/v1/licensing/keys` for the OmniDesk `kid`.
4. Seat accounting: where `DEVICE_LIMIT_REACHED` is decided for OmniDesk activations.

## 2. Target design

### 2.1 Activation (`POST activations`)

1. Authenticate principal (section 2.4). Reject unless the principal is authorized for the organization that owns the referenced license or entitlement.
2. Strict schema, 2048 B cap, `Idempotency-Key` required (16 to 128 chars).
3. `OmniDeskActivationProof::verify`: device possession proof over the canonical message that includes the idempotency key.
4. Resolve the entitlement for **the principal's organization only** (never a client-selected tenant). Capability must equal `omnidesk.remote_access`, status `active`, inside its time window.
5. Seat check inside the same transaction as the bind, under the license row lock: count non-deactivated bindings against `managed_devices` for the plan. Over the limit -> `DEVICE_LIMIT_REACHED`; no row is written and no signature is requested.
6. `OmniDeskActivationBindingStore::bind` (idempotent, exact-match replay).
7. `advanceLease` from sequence 0 to 1, then build claims from stored state, then `OmniDeskEntitlementIssuer::issue(claims, signer)`.
8. Order matters: **reserve the replay cursor before requesting a signature**. A signer failure after the cursor moves forces the client to renew (sequence gap is allowed, reuse is not). Never sign first and persist later.
9. Response is `Cache-Control: no-store, private`. Audit event on every outcome, without payloads.

### 2.2 Renewal (`POST leases/renew`)

Requires a fresh server challenge (`verifyAndConsume`), then `OmniDeskRenewalProof::verify` against the **stored** device public key (never one supplied in the request), then `advanceLease(expected = stored cursor)`, then issue. A stale or reused cursor returns `REPLAY_DETECTED` or `STALE_SEQUENCE`. A revoked license, activation or entitlement returns the matching revocation code and issues nothing, even inside a grace window.

### 2.3 Signer boundary

- Production binding is **absent by default**. With no `OmniDeskSigner` bound the routes keep returning 503.
- The production signer must call an isolated signing service or KMS/HSM and return only the signature. The Laravel app never reads, derives, caches or logs a private key. A private key in an environment variable, config file, database row or repository is a release blocker.
- Test signers live under `tests/` only and use a throwaway key generated per test run.
- `kid` is selected per request, must exist in the published key set, and a revoked `kid` fails closed. Licensing keys and release-signing keys are separate.

### 2.4 Principal authentication (decision D2)

A device-only credential must never select the tenant. Tenant and entitlement come from server-side state bound at enrollment. The authorizer returns `OmniDeskApiPrincipal(actorId, organizationId, canManage)`; any failure maps to `UNAUTHENTICATED` (401) or `FORBIDDEN` (403) with no detail.

## 3. Required negative tests (acceptance, none claimed as passing)

Unit and feature tests, each asserting **no signer call and no persisted row** where applicable:

1. No authorizer bound -> 503. No signer bound -> 503 `ISSUANCE_NOT_CONFIGURED`.
2. Foreign-tenant license or entitlement -> 403/404, no existence oracle.
3. Wrong product, inactive, expired or revoked entitlement or license.
4. Bad device proof, wrong fingerprint, wrong domain tag, tampered idempotency key.
5. Idempotent replay returns the original activation; same key with a different device -> `ACTIVATION_CONFLICT`.
6. Concurrent activations against the last free seat: exactly one succeeds.
7. Replay: reused renewal challenge, stale sequence, reused nonce or `jti`.
8. Signer returns a short or oversized signature, throws, or times out -> 503 with the cursor behaviour in 2.1 step 8 and no partial envelope.
9. Revocation (license, activation, entitlement, `kid`) wins over any lease window.
10. Response bodies and logs never contain a key, signature input beyond the envelope, or tenant data from another organization.

An end-to-end test with a throwaway test signer proves the orchestration only. It is not evidence of production signing.

## 4. Blocker register

| ID | Blocker | Owner | Notes |
| --- | --- | --- | --- |
| D1 | Plan matrix: capabilities, the six limits, lease TTL and offline grace per plan (`Personal_Free`, `Trial`, `Professional`, `Business`, `Enterprise`, `OEM_Custom`) | Business owner | Commercial decision. Must not be invented by engineering. |
| D2 | Principal authentication mechanism for `OmniDeskApiAuthorizer` | Owner and security review | Device-only credentials must not select a tenant. |
| D3 | Signing custody: KMS/HSM or an isolated signer, with `kid` rotation and revocation | Owner | External provisioning and possibly cost. This repository's zero-spend rule means no paid service is assumed. |
| D4 | Publish the OmniDesk verification key set at `/api/v1/licensing/keys` | Owner after D3 | Separate from release-signing keys. |
| D5 | Production restore gates: independent encrypted DB and uploads restore, rollback proof, pointer reconciliation | Owner and CodeBridge lane | `RELEASE_GATE.md` applies. Production release `574e` differs from the protected expected release `8070`. |
| D6 | Seat accounting rule: what counts toward `managed_devices` and how a transfer or deactivation frees a seat | Business owner | Needed for the concurrency test. |

## 5. Rollout and rollback

1. Land D1 to D4 as reviewed source and configuration, still unbound in production.
2. Land the orchestrator with tests; routes stay 503 until both the authorizer and the signer are bound.
3. Staging QA with a staging-only signer and an owner-run authenticated browser session.
4. Bind in production only after D5. Rollback is unbinding the signer (routes return to 503) and revoking the `kid`; existing leases then expire non-destructively per the contract.

No step above is complete. This document does not claim commercial release readiness, live licensing, or that any signing key exists.
