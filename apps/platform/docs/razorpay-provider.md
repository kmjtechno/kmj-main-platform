# Razorpay provider preparation

Razorpay is intentionally **disabled by default**. This integration must not be enabled with live credentials until test-mode checkout, webhook, reconciliation, refund handling, account readiness and owner review are complete.

## Environment

- `RAZORPAY_ENABLED=false`
- `RAZORPAY_KEY_ID=`
- `RAZORPAY_KEY_SECRET=`
- `RAZORPAY_WEBHOOK_SECRET=`
- `RAZORPAY_BASE_URL=https://api.razorpay.com/v1`
- `RAZORPAY_TIMEOUT_SECONDS=10`

Secrets belong in the deployment secret store, never source control or logs.

## Safety contract

Checkout initiation is bound to an existing KMJ commercial order and an active plan for the same product. Amount and currency come from the server-side plan. A local idempotency record is written before the provider request. If provider state becomes ambiguous, automatic retry is blocked to avoid duplicate orders.

Captured payment evidence is accepted only when the provider API or a valid HMAC-authenticated webhook matches the stored Razorpay order, amount and currency. Webhook event ids are replay-protected and only a SHA-256 digest of the raw payload is retained in the event audit table.

The provider adapter produces `ProviderPaymentConfirmation` for the existing `PaymentReconciler`; it does not grant an entitlement. Refund webhooks are tracked durably, but refund initiation is deliberately not exposed in this preparation slice.

## Before enabling

Use Razorpay Test Mode keys first. Configure the webhook endpoint `/api/razorpay/webhook` with a separate webhook secret and subscribe only to the reviewed payment/refund events. Run the full CI suite and an end-to-end test-mode payment. Confirm captured status from trusted backend evidence before fulfillment. Live enablement requires explicit owner approval.
