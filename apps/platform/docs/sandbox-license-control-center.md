# Sandbox License Control Center

This increment provides an owner-scoped sandbox workflow for issuing a short-lived license from an active entitlement, validating the signed token, revoking it, and confirming subsequent validation fails closed.

## Safety boundaries

- Sandbox environment only.
- No production signing keys are used.
- License issuance requires an active entitlement owned by the authenticated organization owner.
- Revocation is persisted and checked during validation.
- Production deployment, DNS, billing, and destructive database actions are outside this increment.

## Critical path

Organization → Product → Entitlement → signed sandbox license → validation → revocation → usable control surface.
