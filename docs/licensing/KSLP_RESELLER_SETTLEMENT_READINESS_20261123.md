# ONE Licensing Hub — reseller settlement safety inspection (source only)

**Date:** 23 November 2026  
**Status:** Independent read-only development slice. **Owner release HOLD** remains in force.

## Why order confirmation cannot become reseller credits

Current `CommercialOrderService::confirm()` accepts a manual order confirmation supplied by an owner; the Razorpay verification/reconciliation flow is **sandbox-only**. Thus `commerce_orders.status=confirmed`, a linked provider order and/or a `payment_webhook_events.processing_status=reconciled` row are **insufficient evidence of live settled, unrefunded customer money**.

`KslpResellerSettlementReadinessInspector` is an internal service that performs bounded **read-only** diagnostics. There is deliberately **no new route, caller, balance, credit grant, trial extension, payment gateway call, production migration or paid signing permission**. Existing KSLP + Main Platform remain the only authority.

Given an actor, KSLP licensed product and commercial order, the inspector:

- Requires the organization's real `license.manage` capability, and matches *both* licensed product and commercial order to the same issuer organization before reading provider records.
- Checks missing/unconfirmed order status, absent price/currency, provider links, link amount/currency mismatch, sandbox vs live source, bounded reconciled webhook receipt counts, and known refund/dispute/chargeback event signals.
- Always reports blockers for **unapproved delegated reseller grant**, missing canonical order↔licensed product SKU policy, unverified **live** merchant settlement, missing full refund/chargeback state machine, and unapproved product-specific license signing.
- Always returns `status=blocked_source_review_only`, `verified_live_settlement=false`, `available_credits=null`, `paid_issuance_enabled=false`. A forged `environment=live` link and `reconciled` inbox row cannot change this.
- Emits bounded generic blocker codes and aggregate counts, **never payment/customer identifiers, provider secrets, raw payload, checkout tokens or a spendable balance**.

## Tests

Laravel negative tests cover pending order, owner-manual confirmation, consistent sandbox reconciled receipt, amount mismatch, refund signal, forged live link, foreign actor and foreign commercial order. All paths must leave `kslp_licenses` and commercial entitlements untouched. Exact-head CI and independent review are required before a source-only merge.

## Missing capabilities for later work

A future real reseller grant must have a stronger tenant/role policy than current developer `license.manage`; an owner-approved canonical KSLP product ↔ commercial SKU/plan/price/currency mapping; provider-verified **live** capture, merchant ID, environment and amount; settlement/finalization evidence; time-bounded replay-proof reconciliation and refunds/chargebacks; and atomic non-negative credit reserves/refunds on the single KSLP ledger. The evidence schema proposed separately in PR #1101 carries **zero** credits and is not an authorization shortcut.

The inspector intentionally cannot turn a positive diagnosis into a grant. **Even if every visible local link appears consistent, the output remains BLOCKED.** This must change only in a separately owner-approved implementation with fully independent financial proof, KSLP signing and device acceptance tests.

References: `PRODUCT_WORKFLOW_AND_PAYMENT_GATES_20261123.md`, `AUTHSP_LEGACY_WORKFLOW_PARITY_LOCK_20261028.md`, and `docs/payments/OWNER_ONE_PLACE_SETUP.md`.
