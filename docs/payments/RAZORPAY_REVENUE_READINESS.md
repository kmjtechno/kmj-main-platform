# KMJ Main Platform — Razorpay revenue integration readiness

**State: Trust boundary implemented in code; live payment collection DISABLED.**

This integration must extend the existing `CommercialOrderService`, organization capability checks, KSLP licensing authority and append-only ledger. It must not introduce a second subscription or licensing authority.

## Merchant-controlled prerequisites

1. Complete Razorpay merchant activation and KYC with accurate legal business details and settlement bank account. International card acceptance and subscriptions may require separate activation/approval. An operator must complete these externally; KMJ must not claim approval or create fictitious merchant identities.
2. Configure separate **test** API key ID, API secret and webhook secret in the approved secure environment. Do not store secrets in git, the public dashboard, device agents, or model output.
3. Publish accurate company identity, contact, digital delivery, refund/cancellation, privacy, terms, subscriptions and tax documentation. Do not imply GST status that has not been verified.
4. Enable live credentials only after test transactions, idempotency, refund and reconciliation checks pass in an isolated environment.

## Payment authority invariant

`Account -> Organization -> Commercial Order -> Verified Captured Payment -> Operator/Approved Fulfillment -> Entitlement -> Signed License -> Device`

- Always create Razorpay Orders **server-side** using the exact server-owned amount, currency, customer and commercial order. Never trust frontend price.
- Use the *stored* Razorpay order ID and `razorpay_payment_id` to verify the callback HMAC; do not take the expected order ID from the browser.
- Validate `X-Razorpay-Signature` against **exact raw request bytes** with the dedicated webhook secret. Do not parse and re-serialize the JSON for authentication.
- Enforce deduplication via provider event ID and provider payment/order IDs, unique constraints, captured-status validation, non-overpayment/amount/currency matching, atomic transitions, and append-only commercial audit. Reject replay, out-of-order events and cross-organization orders.
- Verify captured payments from a trusted Razorpay API response before settlement/fulfillment. Do not grant a license because checkout reports success or a raw webhook is received.
- Treat paid subscriptions as mandatorily consented and revocable; include refund/reversal/chargeback paths that remove rights through the existing KSLP lifecycle.
- No automatic live charge, refund, payout or owner override based on AI-generated instruction alone.

## Implemented first slice

`RazorpaySignatureVerifier` provides dependency-free constant-time verification for checkout signatures and webhook payloads. It performs **no financial writes**, holds **no keys**, and grants **no entitlements**. PHPUnit negative tests reject tampered order/payment IDs, altered JSON bytes, malformed HMACs, missing secrets and oversized webhooks. This is not a live Razorpay integration.

## Work still required before selling

- Razorpay order adapter behind service boundary (sandbox only initially), checkout, server-side payment retrieval, and persistent payment event inbox.
- Replay-safe webhook queue, strict idempotency and mismatch handling, retry policy, reconciliation of payment/capture/refund/subscription events.
- Owner-only Super Admin controls for merchant onboarding readiness, product price/currency and tax rules, order history, disputes, invoices, subscription lifecycle, settlement mismatches, refund approvals, payment logs and audit/export.
- Dedicated staging with independent secrets, database and domain/TLS; real test-key end-to-end evidence, signed-key management, alerting and incident rollback.
- Merchant regulatory review for domestic/international SaaS invoices, tax/export proof and privacy/consumer policies.

## Official technical references

- Razorpay order-first server integration: https://razorpay.com/docs/server-integration/python/test-app/
- Razorpay security checklist: https://razorpay.com/security/checklist/
- Razorpay subscriptions: https://razorpay.com/subscriptions/
- Razorpay international eligibility: https://razorpay.com/learn/breaking-down-the-requirements-for-accepting-international-payments-through-razorpay/

**Cost guard:** API/test implementation may use existing VPS and GitHub included quotas. Razorpay merchant processing fees and applicable tax on successful live payments are not zero, and promotions must not be assumed eligible.
