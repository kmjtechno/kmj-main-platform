# Payment webhooks (Razorpay / Cashfree)

Endpoint: `POST /webhooks/payments/{provider}` where provider is `razorpay` or `cashfree`.

- Authentication: provider HMAC over the exact raw request bytes (no session, no CSRF).
- Secret: encrypted owner vault (`/operator/payments`, webhook secret field). Cashfree falls back to its client secret; Razorpay may fall back to `KMJ_RAZORPAY_WEBHOOK_SECRET`.
- Responses: 200 verified (new or identical replay), 409 same event id with different signed body (conflict row recorded, original untouched), 401 bad signature, 400 signed non-JSON, 503 no secret/table (fail closed; provider will retry), 404 other provider.
- Storage: `payment_webhook_events` keeps provider, event id, type, order/payment ids, payload SHA-256 only. Unique on (provider, event id) gives replay safety.
- Not included: order settlement, entitlement or license issuance. Payment state is not a license; reconciliation must verify with the provider API first.

Owner setup (Razorpay dashboard): add webhook URL `https://kmjtechno.com/webhooks/payments/razorpay`, choose payment.captured / payment.failed / order.paid, set the same secret in the owner console. Live delivery is unproven until a real test event shows up in `payment_webhook_events`.

## Order linkage and reconciliation (sandbox, operator-run)

- `RazorpayCheckoutOrders::open($commercialOrderId, $expectedAmountMinor)` creates one Razorpay sandbox order (receipt = commercial order id) and records it in `commerce_provider_orders`. The amount is a server fact.
- `php artisan payments:reconcile-razorpay [--limit=50]` processes `received` inbox events of type `payment.captured` / `order.paid`. It confirms an order only if Razorpay's API shows that exact payment captured, unrefunded, bound to our provider order, with the expected amount and currency. Outcomes: `reconciled`, `unmatched`, `rejected` (with `processing_note`); provider/vault outages leave the row for a retry.
- Not scheduled and no customer endpoint exists yet. Order confirmation grants no entitlement or license.
