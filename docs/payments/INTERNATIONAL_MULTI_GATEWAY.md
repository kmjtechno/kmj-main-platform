# KMJ TECHNO — International payment-gateway program

## Merchant status and routing (October 9, 2026)

The owner reports **Cashfree and Razorpay merchant accounts already approved**. This is an owner statement, NOT verified gateway API credentials, cross-border capability activation or successful payment test.

| Provider | Role | Activation requirement |
| --- | --- | --- |
| Razorpay | India domestic UPI/cards and approved international checkout | Merchant account is owner-reported approved; complete separate API credentials, webhook, verified currency and international-card acceptance checks |
| Cashfree | India backup; preferred cross-border card/multi-currency and possible PayPal wallet support | Account owner-reported approved; international cards/Global Collections, recurring and PayPal modes must each be independently confirmed as enabled |
| PayPal | Additional wallet for international buyers only | Indian business merchant activation, applicable KYC and purpose code; no domestic Indian receiving |
| Paddle | Optional SaaS Merchant of Record for subscriptions | Distinct agreement, merchant review, tax/fee model, product eligibility and payout acceptance |
| Stripe | Future card/recurring provider | Invite-only onboarding for India; not an immediate dependency for launch |

Razorpay and Cashfree should be available as **independent, explicitly approved checkout choices** once verified. Never reroute a failed or pending provider order automatically: reconcile/refund/cancel the authoritative commercial order first, then create a new provider attempt with a separate idempotency key and preserved audit trail.

**Live charging is OFF in this implementation**. The owner-only `/operator/payments` console is read-only and never exposes secrets, payment IDs, or merchant banking details. It reports owner-attested merchant approval separately from server credential presence and actual transaction verification. This is a prerequisite, not live payment processing.

## What this branch adds

1. `CashfreeSignatureVerifier`: verifies exact `x-webhook-timestamp + raw request body`, HMAC-SHA256/base64, using the correct Cashfree client secret, rejecting malformed signatures/headers and oversized content.
2. `PaymentWebhookSignatureRouter`: dispatches **only** Razorpay (raw-body HMAC-SHA256/hex) or Cashfree (timestamp+body HMAC-SHA256/base64); PayPal/Paddle/Stripe events cannot be marked verified until dedicated provider adapters exist.
3. `CashfreeSandboxOrderClient`: fixed `https://sandbox.cashfree.com/pg/orders` URL, API version `2025-01-01`, server-owned order ID/amount/currency, idempotency key and strict response validation. Supports INR test orders only; no API route, live URL, charging, reconciliation or entitlement issuance.
4. `PaymentGatewayReadiness`: secret-free, owner-only readiness summary showing Cashfree, Razorpay and possible global providers. Existing operator page gains a payment-console link. Passkey, verified email and recent password confirmation remain required.

**Environment controls (store securely on VPS, do not commit):** `KMJ_CASHFREE_CLIENT_ID`, `KMJ_CASHFREE_CLIENT_SECRET`, `KMJ_RAZORPAY_KEY_ID`, `KMJ_RAZORPAY_KEY_SECRET`, `KMJ_RAZORPAY_WEBHOOK_SECRET`. International capabilities are recorded only by audited manual verification; no public switches are activated by merely setting booleans. `KMJ_PAYMENT_LIVE_CHARGING_ENABLED` does not create any charge endpoint and must not be treated as production authorization.

## Razorpay sandbox order slice (2026-10-09)

`RazorpaySandboxOrderClient` creates Orders API requests with **only** `rzp_test_` credentials; `rzp_live_` keys are rejected before any HTTP request. It accepts only trusted server-side INR/paise/receipt values, sends `partial_payment=false`, and validates provider response ID, amount, currency, receipt, `created` status and amount paid/due. PHPUnit uses mocked HTTP and does **not** prove a real sandbox key works. There is no public checkout route and no automatic entitlement issuance. Local commercial-order-to-provider-receipt idempotency and actual sandbox payment/webhook reconciliation remain mandatory before activation.

API reference: https://razorpay.com/docs/server-integration/python/test-app/ and https://razorpay.com/docs/api/orders/fetch-with-id/

## Required before launch

- Complete Cashfree and Razorpay **sandbox** create-order/checkout, client return, raw-body signed webhook, server-side GET payment verification, capture/reconciliation and duplicate/retry tests with actual merchant test keys.
- Independent international enablement and supported method/currency/country verification; settlement records/FIRC or equivalent evidence and merchant bank compliance.
- Provider event inbox/outbox with immutable records and provider-scoped unique event IDs; strict customer/order, amount-minor, currency, environment, provider account and capture-state matches; no trust in UI callback alone.
- Idempotent ledger transitions, immutable financial audit, refund/chargeback/dispute handling, subscription renewal/cancellation, explicit buyer consent, prorations and cross-border tax/invoicing with professional legal review.
- Super Admin ability to manage plan amounts, currencies, provider mode, country eligibility, routing priority, subscriptions, invoice/refund approval, disputes, failure alerts and payout reconciliation, with audited MFA owner authorization and security separation.
- Complete isolated staging, no copied production merchant credentials, live canary with customer-approved small transactions and observed rollback. Never automatically spend or run an unapproved live transaction.

## Trust boundaries

`Account → Organization → server-created Commercial Order → provider checkout → independently verified captured funds → reconciled order ledger → governed entitlement → signed license → device activation`

Never grant license access from an unverified webhook or hosted checkout callback. Never send a Cashfree secret, Razorpay webhook secret or PayPal OAuth secret to the browser/AI agent. Do not use the same signing formula for different gateways.

## Official references

- Cashfree webhook verification: https://www.cashfree.com/devstudio/preview/pg/tools/webhookVerification
- Cashfree sandbox Create Order: https://www.cashfree.com/devstudio/preview/pg/web/checkout
- Cashfree cross-border: https://www.cashfree.com/accept-international-payments/
- PayPal receiving in India: https://www.paypal.com/in/cshelp/article/can-i-use-paypal-to-receive-payments-from-indian-customers-help1049
- Stripe India access: https://support.stripe.com/questions/moving-to-invite-only-in-india
- Paddle pricing: https://www.paddle.com/pricing

**Additional cloud spend policy:** $0 above existing VPS and included GitHub Pro budgets, while actual merchant processing fees, refunds, FX and taxes apply when customers are charged. Project-wide source of truth: GitHub Issue #341.
