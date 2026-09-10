# services/license-core

Security-sensitive licensing/verifier core. The implementation target is Rust with thin language/platform wrappers.

Responsibilities:
- Parse and verify compact signed license/lease artifacts.
- Enforce expiry, product/entitlement binding and revocation inputs.
- Provide deterministic test vectors and wrapper conformance.

Rules:
- No custom cryptographic primitives.
- Signing private keys must not live in application databases or source control.
- Code-signing and license-signing keys are separate.
- Hardware-backed device keys/attestation are optional strengthening mechanisms, not the only activation path.
- Do not claim licensing is unbreakable.
