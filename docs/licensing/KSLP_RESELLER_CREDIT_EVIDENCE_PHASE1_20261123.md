# ONE Licensing Hub — reseller credit evidence foundation (source only)

**Date:** 23 November 2026  
**Gate:** OWNER RELEASE HOLD; **no staging, production migration, signing, billing activation, or commercial license issuance**.

## Why a separate evidence layer?

The existing `CommercialOrderService::confirm()` accepts an operator-supplied confirmation reference as well as provider-reconciled sandbox evidence. Its `confirmed` state **cannot alone prove** the captured, unrefunded, correctly settled merchant funds needed to fund a reseller. A developer issuer subscription and its monthly quota are likewise **not** a paid reseller wallet.

This slice therefore introduces an organization-scoped, **zero-credit** KSLP evidence inbox, not a second payment, issuer, or customer entitlement authority:

- `kslp_reseller_credit_ledger` is an append-only *application-contract* audit table (its source API only inserts, with no edit, delete, credit, debit, or cash-out method). Database superusers may still mutate tables; this is **not** claimed to be tamper-proof.
- `KslpResellerCreditEvidenceLedger::queuePending()` requires the real `license.manage` capability and matching organization ownership of **both** the licensed product and commercial order. The order must be `requested` or `confirmed`; cancelled orders are denied.
- Every entry is `evidence_pending` / `unverified` with `credits_delta = 0`. It stores a SHA-256 digest of the idempotency key, not the raw key or provider credentials. An order+product may be queued only once. Exact retries succeed; collisions or cross-order reuse fail closed.
- `snapshotForActor()` returns a tenant-only pending count. `available_credits = null` and `paid_issuance_enabled = false`, **even when an order was manually confirmed**.
- **No HTTP routes**, reseller portal, balance, payment callbacks, credit issuance, key signing, new entitlement/subscription, or rollout switch are introduced.

## Acceptance and next phases

Phase 1 tests: owner-scope only, foreign order/foreign user denied, exact-idempotency retry, collision and cancelled order denied, zero credit after manual confirmation, migration/rollback and CI.

Phase 2 (NOT IMPLEMENTED): approved reseller role/staff with finer permissions and per-product grant; owner-approved credit SKU, integer unit denomination, region/currency/tax and price; raw-body signed webhook + server-to-server provider GET for captured funds; exact merchant/environment/amount/order/product/customer match; trusted settlement record with duplicate/replay controls, refund and chargeback state machine. A sandbox event cannot fund a real wallet.

Phase 3 (NOT IMPLEMENTED): atomic approved credit grant/reversal/reservation with non-negative balance and concurrent transaction tests; ledger reconciliation and owner review; eventual verified order → KSLP subscription/entitlement → product-specific signed lease after all signing/device gates. Never treat an order, arbitrary HMAC, trial key, issuer monthly quota or pending evidence as spendable credits.

This is a backend foundation for the AuthSP-inspired reseller workflow under **one** KSLP authority. The existing source docs `PRODUCT_WORKFLOW_AND_PAYMENT_GATES_20261123.md` and `AUTHSP_LEGACY_WORKFLOW_PARITY_LOCK_20261028.md` remain controlling.
