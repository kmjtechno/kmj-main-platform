# CodeBridge licensing integration (draft)

This additive adapter uses Main Platform's existing `KslpSigner` interface to produce
CodeBridge's v1 compact Ed25519 JWS. CloudOS KSLP codec/audience behavior is unchanged.
Keys stay with Main Platform. The encoder validates authorized claims; it does not
decide purchase or trial eligibility.

## Renewal service and API

`POST /api/v1/codebridge/renew` accepts the existing CodeBridge client contract:
`{product: "KMJ_CODEBRIDGE", tenant, device, sequence}` and returns `{token}`.
Authentication uses a distinct random device service credential in the Bearer header.
Only its SHA256 digest is stored. Request bodies are limited to 4096 bytes and the
route is throttled. Replies do not include raw errors or log credentials.

The service looks up the credential, authoritative KSLP license and activation, then
the active `codebridge.<plan>` policy. It checks tenant/device/product binding,
credential/license expiry and revocation, activation identity/deactivation, feature
policy and device count. Lease sequence allocation and audit insert share one
transaction; signer/audit errors roll back. Client-supplied sequence cannot advance
the authoritative counter. A lost response may be retried with the old sequence and
receives a newer lease, never a replay of a write on the customer's device.

Lease duration is capped at 24 hours and commercial/credential expiry; signed grace
is capped at 48 hours, commercial grace and credential expiry. Already-issued offline
leases are not immediately revoked by an unsigned HTTP denial. Separate signed
revocation distribution remains outstanding.

## Operator prerequisites (no automatic commercial grants)

- Apply the additive migration after normal platform review/backup gates.
- Register the CodeBridge product and authoritative purchased/trial license through
  approved commercial controls; no seed creates a paid license or a trial here.
- Set active `plans.code` to `codebridge.<plan>` with boolean read/write/execute
  features and integer devices/concurrent_jobs limits (concurrency 1–16).
- Enroll an actual activated device, store its matching license/activation/tenant,
  registered server identity, unique device ID, credential hash and credential expiry.
  Enforce device limits when enrolling as well as during renewal. Enrollment UI and
  proof-of-possession provisioning are not implemented by this patch.
- Bind a reviewed production `KslpSigner` in the application container; no development
  key, sandbox HMAC secret or automatic fallback is provided.
- Enable `CODEBRIDGE_LICENSE_API_ENABLED` only after HTTPS, database and HTTP tests
  pass. The API returns unavailable while disabled or without a signer.
- Obtain the initial lease through this same service before configuring the agent's
  token file. Preserve its lease_sequence on credential rotation; never reset it.
  Configure the agent renewal URL and private service credential outside project roots.

## Evidence and remaining gates

Cloud workspace PHP 8.3.6+sodium/PDO SQLite: 15 encoder cases, 27 renewal scenarios
and 3 Node consumer checks passed. Node verifies an actual database-authorized renewal signature against
CodeBridge commit a09fae60677ed2ab17a3a4c9601afea793e62a55. Test keys are ephemeral and
only public verification material is passed between processes.

GitHub run 36562077316 failed before executing steps; no remote CI pass is claimed.
Full Laravel HTTP/kernel tests, migrations on real platform databases, MySQL/Postgres
locking/concurrency, production key binding and end-to-end enrollment/payment testing
remain required. The SQLite tests exercise the service against real SQL but do not
constitute those platform gates. This draft has not been deployed or enabled.

## KSLP CI compatibility follow-up

Existing KSLP boundary arrays now declare their value types; optional lease dates
accept CarbonInterface and use integer timestamps. Empty or wrong-length activation
signatures return the protocol denial before calling sodium. The standalone
activation-proof test reproduces the previous SodiumException and now passes five
signature cases with a stub database; it does not replace Laravel transaction tests.
Missing contract-file reads return unavailable. These changes do not disable any
static-analysis rules or regenerate trusted contract checksums.
