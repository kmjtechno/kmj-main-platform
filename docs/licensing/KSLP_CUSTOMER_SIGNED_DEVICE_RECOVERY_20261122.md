# KSLP Customer Device Transfer — signed recovery source-only

Status: DEFAULT OFF. This is source under review, not installed or enabled
on KMJ-elite, not complete native SDK integration and not commercial release.

This KSLP-v1 CloudOS customer transfer service uses the *same* KMJ Main
Platform license tables, server authorization, activation challenge and
audit ledger. No legacy AuthSP login, HWID reset, private keys, database
or payment credentials are imported.

## Trust boundary

Only email-verified, reauthenticated customers may transfer their own
active non-trial KMJ_CLOUDOS KSLP license. Organization licenses require
current organization membership plus license.manage capability.

The owner rollout config KMJ_CUSTOMER_DEVICE_TRANSFER_ENABLED is false
by default and must remain so until independently reviewed client SDKs and
an owner-approved signed release are verified.

The protected, CSRF-checked, 3/min rate-limited web endpoints are:

- POST /licensing/devices/transfer/{license}/challenge
  Accepts the NEW device Ed25519 public identity, returns a 5-minute
  server-stored single-use challenge, nonce and signed protocol domain
  KSLP-ACTIVATE-v1.
- POST /licensing/devices/transfer/{license}/complete
  Requires the NEW device signature on the exact
  KSLP-ACTIVATE-v1|license_id|nonce challenge, a hashed machine ID,
  UUID request idempotency key and 8–240 character audit reason.

The client keeps its Ed25519 private key locally. A caller cannot pass
a false device secret, skip signed proof or transfer an unrelated license.

In a PostgreSQL transaction the server locks the original license,
rechecks ownership, plan, status, active activation and the 24h
server-enforced transfer cooldown. It then consumes the challenge
atomically, replaces the old binding, records an event and advances
the monotonic sequence. A failure leaves the original binding and
unused challenge intact. An exact retry cannot double-increment.

Success returns only activation_id, signed_lease_issued=false, and
device_transfer_recorded_pending_signed_lease. It does not create a
CloudOS signed lease, infer online device presence or expose hardware
identities, bootstrap secrets, keys or previous device details.

Cached signed offline leases can remain valid until their independent
24h expiration even after an online sequence advance. Clients must
enforce the stored trusted minimum sequence and clock-rollback policy.

## Must remain blocked before LIVE

Independent exact-head CI, customer role/tenant/race/invalid-signature
tests, genuine .NET/C++/Rust signed SDK conformance, complete owner
review of scope and abuse protections, stable staging, disposable
PostgreSQL+uploads restore, rollback, owner-signed immutable release
and KMJ-elite live readback. No Google VPS for Main Platform.

A UI-based reset is deliberately not advertised as active until
the approved native client can actually generate and submit its proof.
No billing, reseller grant, customer deletion or root deployment is
performed by these source changes.
