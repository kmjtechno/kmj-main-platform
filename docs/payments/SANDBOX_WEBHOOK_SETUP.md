# KMJ sandbox webhooks — Razorpay & Cashfree

This procedure applies **only after PR #425 is merged, the migration is deployed, and the endpoint has passed signed sandbox smoke tests**. The URL below is not an active endpoint until those conditions hold. **Live charging remains disabled.**

## Razorpay (TEST mode only)

1. In KMJ Super Admin → Payment Gateways → Razorpay, store the `rzp_test_...` key ID and matching sandbox API key secret in the encrypted credential vault.
2. Generate a separate long random webhook secret (at least 32 unpredictable characters) **locally** in a password manager. Save it as Razorpay's **Webhook Secret** in the KMJ encrypted settings, and use the exact same value in the Razorpay Test-mode webhook form. Never paste keys or secrets in chat, tickets, git, or logs.
3. **Once HTTPS routing and signature tests are verified**, set Webhook URL to `https://kmjtechno.com/api/payments/webhooks/razorpay`.
4. Alert Email: use an inbox you monitor. Under Active Events select **only** `payment.captured` and `payment.failed` for this initial receiver. Additional event classes (orders/refunds/disputes) are deliberately *not* consumed here.
5. Create the Test-mode webhook and conduct an owner-authorized full sandbox test payment using a server-created order, then inspect both provider delivery status and `payment_webhook_inbox` entries. New signed deliveries return HTTP 202; exact duplicates return 200. Invalid signatures, missing configuration and replay conflicts must fail closed.
6. The inbox state is `received_unreconciled`, **not** paid or fulfilled. No product license is granted. Independent trusted-API payment reconciliation, dispute/refund processing, ledger, and owner acceptance remain required before live commercial activation.

## Cashfree (sandbox only)

- Use the Cashfree PG sandbox webhook configuration and `https://kmjtechno.com/api/payments/webhooks/cashfree` **only after deployment/HTTPS validation**.
- The receiver verifies Cashfree PG's `x-webhook-timestamp` + exact raw bytes via HMAC-SHA256/base64 with the stored **sandbox client secret**; there is no public/shared secret shown to the browser.
- Initially support only `PAYMENT_SUCCESS_WEBHOOK`, `PAYMENT_FAILED_WEBHOOK` and `PAYMENT_USER_DROPPED_WEBHOOK` with valid matching event statuses and payment/order identifiers. Always verify actual dashboard event options and run a signed sandbox delivery test.

## Release acceptance

Exact SHA CI or approved equivalent isolated tests, PHP/Pint/PHPStan/TypeScript, PostgreSQL migration and rollback, masked-secret storage validation, authenticated owner UI, Nginx HTTPS routing, test delivery, duplicate/tamper/replay tests, backups/rollback. No direct live card charge, capture, refunds, entitlement grant, or production charging on this endpoint.
