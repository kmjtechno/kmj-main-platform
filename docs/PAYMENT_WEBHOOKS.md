# Payment webhooks (Razorpay / Cashfree)

Endpoint: `POST /webhooks/payments/{provider}` where provider is `razorpay` or `cashfree`.

- Authentication: provider HMAC over the exact raw request bytes (no session, no CSRF).
- Secret: encrypted owner vault (`/operator/payments`, webhook secret field). Cashfree falls back to its client secret; Razorpay may fall back to `KMJ_RAZORPAY_WEBHOOK_SECRET`.
- Responses: 200 verified (new or replay), 401 bad signature, 400 signed non-JSON, 503 no secret/table (fail closed; provider will retry), 404 other provider.
- Storage: `payment_webhook_events` keeps provider, event id, type, order/payment ids, payload SHA-256 only. Unique on (provider, event id) gives replay safety.
- Not included: order settlement, entitlement or license issuance. Payment state is not a license; reconciliation must verify with the provider API first.

Owner setup (Razorpay dashboard): add webhook URL `https://kmjtechno.com/webhooks/payments/razorpay`, choose payment.captured / payment.failed / order.paid, set the same secret in the owner console. Live delivery is unproven until a real test event shows up in `payment_webhook_events`.
