# First Vertical Slice

Target:

`Organization -> Product -> Entitlement -> Signed sandbox license -> Product validation -> Revocation`

## Acceptance sequence
1. Create an organization under an authenticated account.
2. Register one sandbox product in Catalog.
3. Issue an entitlement through an explicit policy result.
4. Create a sandbox license derived from that entitlement.
5. Sign the license through the licensing boundary; private signing material must not live in application tables or source control.
6. Validate the license through the Rust verifier contract.
7. Revoke the license and prove subsequent validation fails deterministically.
8. Record entitlement, licensing, revocation and approval/audit events.

## Non-goals for this slice
- Production payments.
- Production DNS/cutover.
- Cloud Nexus integration.
- Real customer migration.
- Claims of unbreakable licensing.

## Required tests
Tenant isolation, authorization, idempotency, entitlement-policy invariants, license vectors, revocation behavior, audit completeness and rollback-safe migrations.
