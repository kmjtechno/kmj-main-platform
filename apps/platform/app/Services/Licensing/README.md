# Sandbox licensing boundary

This implementation is intentionally sandbox-only.

- It signs license payloads with an injected HMAC secret.
- It validates signature, expiry, environment, and persisted revocation state.
- It does not access or manage production signing keys.
- Production asymmetric signing and key custody remain owner-gated/high-risk work.
