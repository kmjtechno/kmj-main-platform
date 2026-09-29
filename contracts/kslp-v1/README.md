# KSLP-v1
Canonical KMJ Main Platform ↔ KMJ CloudOS commercial licensing contract.
Main Platform is the authority; CloudOS verifies signed leases and enforces entitlements.
Algorithm: Ed25519 only. Private license-signing keys are never part of this contract or customer artifacts.
License, release/update, and evidence signing are separate trust domains.
State machine: ACTIVE → RENEWAL_DUE → GRACE → RESTRICTED → REACTIVATED/REVOKED.
Restricted mode MUST NOT delete, corrupt, encrypt, or disable recovery/export of customer websites, databases, or backups.
Plans: trial (30-day default), professional, business, enterprise, custom_oem.
Breaking changes require a new protocol version; KSLP-v1 parsers fail closed on unknown fields/algorithms.
