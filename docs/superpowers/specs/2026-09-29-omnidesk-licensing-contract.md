# KMJ OmniDesk Main Platform Licensing Contract

**Status:** v1 contract defined; production signing remains owner-gated.

## Authority

KMJ Main Platform is the **billing and licensing control plane only** for KMJ OmniDesk. Its OmniDesk responsibilities are limited to plans/subscriptions, payment reconciliation, entitlements, license issuance, licensing-bound device activation, lease renewal, revocation, commercial audit, and signing-key custody.

It is explicitly **not** an OmniDesk runtime or remote-session backend.

Canonical identity:

- slug: `kmj-omnidesk`
- product ID: `KMJ_OMNIDESK`
- capability: `omnidesk.remote_access`
- protocol: `KSLP-v1`
- contract: `kmj.omnidesk.license.v1`

OmniDesk is a separate product/runtime repository. It consumes released Main Platform billing/licensing APIs and contracts and must never read Main Platform databases directly.

### Hard runtime boundary

The following responsibilities are forbidden in KMJ Main Platform for OmniDesk:

- remote-session transport and session signaling;
- P2P connectivity and NAT traversal runtime;
- relay data plane;
- screen/video/audio streaming;
- remote input and clipboard transport;
- file-transfer data plane;
- media encoding/decoding;
- OmniDesk device/session runtime.

Those responsibilities belong outside Main Platform. No future OmniDesk feature may expand Main Platform beyond the billing/licensing control plane merely for implementation convenience.

## Production signing boundary

Production license artifacts use Ed25519 signatures. Private signing keys remain isolated in KMS/HSM, are never stored in application rows, never shipped to OmniDesk, and are selected by versioned `kid`. Verification-key rollover supports overlap; revoked keys fail closed. Release signing and license signing should use separate keys.

## Commercial path

`Plan/payment -> reconciliation -> explicit entitlement -> device activation -> signed entitlement/lease -> local OmniDesk enforcement`

Payment confirmation is not itself an entitlement or license.

## Activation binding

First install creates a local asymmetric device keypair. Main Platform activation binds:

- license and entitlement;
- customer/organization;
- `KMJ_OMNIDESK`;
- activation ID;
- device public-key fingerprint;
- installation identity;
- plan/capabilities/limits.

Activation is idempotent and enforces device limits, duplicate activation policy, replay controls, and suspicious-activation rate controls.

## Signed entitlement

Required security claims include contract/protocol version, `jti`, `kid`, license/entitlement/customer/organization, product identity, plan, activation/device/install binding, capabilities, limits, `iat`, `nbf`, `exp`, lease expiry, nonce, and monotonically increasing sequence.

## Lease and offline grace

Main Platform issues short-lived renewable leases. OmniDesk may cache the last-known-good signed authorization. Central unavailability follows:

`ACTIVE -> RENEWAL_DUE -> GRACE -> RESTRICTED -> REACTIVATED/REVOKED`

Grace duration is server policy/plan-driven. Clock rollback cannot extend grace. Expiry is non-destructive.

## Revocation

License, entitlement, activation, transfer, and signing-key revocations are explicit. A known revocation overrides offline grace. Revocation is audited and non-destructive to customer data.

## API surface

- `GET /api/v1/licensing/keys`
- `POST /api/v1/licensing/omnidesk/activations`
- `POST /api/v1/licensing/omnidesk/leases/renew`
- `GET /api/v1/licensing/omnidesk/activations/{activation_id}/status`
- `POST /api/v1/licensing/omnidesk/activations/{activation_id}/deactivate`
- `POST /api/v1/licensing/omnidesk/activations/{activation_id}/transfer`
- `GET /api/v1/licensing/omnidesk/entitlements/current`

All private endpoints enforce authorization and tenant isolation. Activation is idempotent. State changes emit immutable audit events. Deterministic error codes are used. Secrets and raw signed tokens are redacted from logs.

## Implementation boundary

This document defines the production contract; it does not activate production signing. Existing sandbox licensing code remains sandbox-only until the production signer/key-custody gate is explicitly completed and verified.

The client-side canonical machine-readable contract lives in `kmjtechno/kmj-omnidesk/protocol/licensing/omnidesk-licensing-v1.yaml`.
