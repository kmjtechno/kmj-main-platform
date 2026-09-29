# CodeBridge entitlement encoder integration

This additive adapter uses Main Platform's existing `KslpSigner` interface to produce
CodeBridge's v1 compact Ed25519 JWS. It deliberately does not modify KSLP-v1 CloudOS
audience, codec, claims or issuer behavior. Signing keys stay with Main Platform.

The encoder accepts already-authorized claims and validates binding, feature/limit
shape, a maximum 24-hour lease and maximum 48-hour signed grace. It does not grant
purchase/trial eligibility, validate a customer's authentication, maintain sequence
numbers, enroll devices or expose a renewal API. The service integrating it must
atomically read entitlement/activation state, reject revoked or expired licenses,
bind tenant and device from trusted records, allocate monotonic lease sequences,
cap validity against commercial policy and audit issuance before returning a token.

The isolated CI job generates only an ephemeral test key. It checks PHP rejection
cases, then verifies the produced token with the exact public CodeBridge consumer
commit a09fae60677ed2ab17a3a4c9601afea793e62a55. No private key is emitted or committed.
This proves encoder/consumer compatibility, not an operational billing endpoint.
