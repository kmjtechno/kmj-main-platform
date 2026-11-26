# Refund workflow: design and open decisions (26 Nov 2026)

Status: `PLANNED`. Nothing is implemented. Verified in code on main: there is no refund
workflow; `RazorpayPaymentAdapter` only reads `amount_refunded` to refuse settling an
already refunded payment; the customer cancellation mail says refunds are handled
separately and is not a refund confirmation. Order statuses are `requested|confirmed|cancelled`.

## Why it is not built yet
A refund moves money and may revoke access. The roadmap rule is payment state is not a
license. Two business decisions are needed first; guessing them would be unsafe.

## Decisions needed from the owner
1. After a refund, is the license revoked automatically, or only after an owner action?
2. Who may approve a refund: Platform Owner only, or finance staff too? Any amount limit?
3. Partial refunds: supported or full only?
4. Refund execution: manual (owner refunds in the provider dashboard and records it here)
   or via provider API later. Recommended first slice: manual recording.

## Recommended first slice (small, safe)
- Append-only refund ledger table: order id, amount minor units, currency, provider
  refund reference (optional), reason, recorded by, timestamp. No update/delete.
- Owner-only action "Record refund" on an order; amount cannot exceed the confirmed
  amount minus earlier refunds; idempotent request key.
- Audit event on every record; no provider call, no money movement from this code.
- Licenses are untouched. A separate explicit owner action revokes, per decision 1.
- Webhook receipt for a provider refund event is stored as evidence only and never
  changes order or license state by itself.

## Evidence needed before calling it done
Feature tests on PostgreSQL in CI (limits, idempotency, tenant isolation, owner-only),
migration rollback test, and a sandbox provider refund event fixture. No live refund.
