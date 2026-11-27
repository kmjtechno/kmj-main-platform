# Payment webhook → order settlement: what exists and what does not (2026-11-27)

Status: honest inventory, not a design change. Verified against main at the time of writing.

## What is true today
- Provider webhooks (Razorpay, Cashfree) are verified and stored as inbox events. A verified event shows as **Received**; it does not by itself confirm an order, grant an entitlement or issue a license.
- Razorpay: `RazorpayWebhookReconciler` can confirm a commercial order, but only from independently retrieved, captured, unrefunded provider evidence AND a sandbox-environment link. The scheduled command `payments:reconcile-razorpay-sandbox` **skips in production by design**.
- Cashfree: **no reconciler exists.** Webhooks stay Received.
- Production orders are confirmed by the owner's manual confirm step (receipt reference), not by a webhook.
- Refund records and revoking access are separate explicit owner actions; neither is triggered by a webhook.

## Why the production gate is not loosened
Settling an order from a provider event in production would feed entitlement and seat allocation (for example `HostedTeamSeatAllocator`). That needs the evidence rules of RELEASE_GATE.md first: a live Test Mode payment proof, amount/currency/order-id binding, replay protection and a rollback path. None of that is proven live.

## Remaining blockers before automatic settlement could be considered
1. Owner runs a Razorpay Test Mode payment and the result is read back (not done).
2. Live-mode reconciler design with idempotency, amount/currency binding and refund/dispute handling, reviewed by the owner.
3. A Cashfree reconciler with the same evidence rules.
4. Owner approval of the design change. Until then production stays manual-confirm.

Nothing in this document is a claim that payments are production ready.
