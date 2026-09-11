# services/license-core

Security-sensitive sandbox licensing/verifier core implemented in Rust with thin language/platform wrappers.

Responsibilities:
- Parse and verify the compact sandbox license artifact emitted by the Laravel sandbox issuer.
- Verify HMAC-SHA256 signatures using established crates; no custom cryptographic primitives.
- Enforce sandbox environment, expiry, product binding, entitlement binding, and caller-supplied revocation state.
- Provide deterministic cross-language test vectors and stable failure reasons.

Current boundary:
- This verifier is sandbox-only and does not introduce production signing material.
- The operational verifier secret is injected by its caller and must not be stored in source control or application tables; deterministic test-only fixtures may use non-secret sample material.
- Production asymmetric signing/key custody remains owner-gated high-risk work.
- Code-signing and license-signing keys remain separate concerns.
- Hardware-backed device keys/attestation are optional strengthening mechanisms, not the only activation path.
- Do not claim licensing is unbreakable.

Run locally:
`cargo test --manifest-path services/license-core/Cargo.toml --locked`
