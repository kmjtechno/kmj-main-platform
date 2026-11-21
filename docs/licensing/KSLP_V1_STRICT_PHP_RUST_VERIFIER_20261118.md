# KSLP-v1 strict signed verification — 18 Nov 2026

**Status: STACKED DRAFT / NON-PRODUCTION.** Keep `KSLP-v1` exact CloudOS golden vector stable. This is secure-parser compatibility work, not a replacement issuer and not a claim of impossible-to-crack local DRM. Historical AuthSP supplies **only application/customer/reseller task order**, never signing algorithms, authentication, database, keys, tokens, or deployment.

## Boundary and verified source baseline

- One authority: KMJ Main Platform Laravel/PostgreSQL/KSLP. Existing PHP issuer `KslpCodec` signs Ed25519 `base64url(header).base64url(payload)`, using compact JSON and a server-private key. Rust `services/license-core/src/kslp.rs` verifies it on the CloudOS audience. The legacy v1 fixture is `contracts/kslp-v1/golden-vector-001.json`.
- `KslpOfflineLeaseGuard` independently requires trusted local time/checkpoint, minimum sequence, license+activation identity, signed lifetime cap (24 hours), and known revocation state; this change does **not** replace persistent OS-protected checkpoint storage or server reconciliation.
- The KSLP-v2 COSE/CWT roadmap remains separate; no silent v1 token reinterpretation or algorithm fallback.

## Hardened behavior proposed in this source draft

1. **PHP signature-first entitlement semantics.** Verify a properly sized detached Ed25519 signature against a trusted, bounded `kid` public-key lookup before consuming payload claims as permissions. The token length is capped at 16 KiB. Unknown v1 claim keys, malformed signed types, missing required fields and invalid sequence/time are rejected.
2. **Canonical unpadded Base64URL tokens.** Reject padded, non-URL alphabet and alternate/noncanonical encodings. The existing PHP issuer and Rust verifier already use unpadded URL-safe Base64; golden signatures are not changed.
3. **Rust verifier parity.** Validate bounded token, issuer-era signed time relationships, non-empty identity fields, positive sequence and distinguish `KSLP_WRONG_AUDIENCE` from wrong product. Rust remains algorithm-strict and denies unknown typed claim fields.
4. **Negative cryptographic tests.** Use ephemeral or deterministic **test-only** Ed25519 keypairs to generate signed malformed inputs and demonstrate that a valid signature alone does not grant rights if the envelope is invalid. Existing exact PHP/Rust golden vectors must remain identical.

## Explicit constraints

- A private signing key must never be sent to the SDK, browser, public artifact, GitHub repository, legacy ZIP, application binary or device.
- A valid signed offline license cannot be revoked instantly while offline. Use bounded lease expiry, OS-protected minimum sequence/trusted-time checkpoints, server-side authenticated renewal and safe restricted mode (no destructive customer data behavior).
- Ed25519 signature validity is necessary, not sufficient: device proof-of-possession, product, audience, seat count, paid entitlement, activation revocation, rate limits, tenant and owner policy must be enforced by the appropriate server paths.
- PHP `json_decode` still overwrites duplicate object members, but this **source proposal** checks the original signed header and claims bytes against exactly reconstructed, recursively sorted canonical JSON **after Ed25519 verification**, rejecting duplicate top-level and nested names, noncanonical whitespace and escape spellings. Rust applies the same signed-byte canonical comparison before parsing typed entitlement claims. Positive legacy golden vectors and independently signed negative fixtures must PASS on the **exact same PR head** before calling the gap resolved. Cross-language numeric/Unicode edge vectors and independent fuzz review remain a release gate.
- The npm `picomatch` security audit vulnerability GHSA-fc5q-39xc-vjpf (issue #893) remains unpatched by this change. Never suppress the audit, use forced breaking downgrades or treat isolated test success as a production approval.
- Existing protected production release stays CE6 until independent P520 recovery, staged owner QA, approved release manifest and rollback gates all pass.

## Acceptance before merge or release

- PHP unit and existing feature suite, Rust `cargo fmt --check`, `cargo test --locked`, cross-language golden-vector and negative tests **on the exact immutable PR head**.
- Security review for header and claim parsing, signature correctness, key ID lookup and no customer secret leakage.
- Independent PostgreSQL 18 and frontend/browser test matrix; production security audit clear without bypass; signed SDK interoperability, browser owner acceptance and protected release pipeline gates.
