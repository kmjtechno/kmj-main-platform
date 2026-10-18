# KMJ TECHNO — Razorpay + Cashfree Owner Setup

**Status:** source implementation in PR; production not activated until an independently verified release. The setup panel can create explicit sandbox-only test orders once owner test credentials are configured. It does not process live payments.

## Merchant onboarding — two independent providers

The protected `/operator/payments` page offers a short guided flow for Razorpay and Cashfree. Both connections still require the merchant owner to create/test credentials in the **official provider dashboard**. There is no blanket payment-provider OAuth authorization grant and no safe automatic secret import.

### Razorpay

1. Open https://dashboard.razorpay.com/app/account-settings
2. Turn on **Test Mode** (Razorpay separates live and test keys); under **Website and app settings** open **API keys** and generate Test Mode API Key ID and Secret.
3. In KMJ `/operator/payments`, select Razorpay → **Save keys in KMJ**, fill the write-only Test Key ID and Test Secret, and save. The server enforces `rzp_test_` IDs; it rejects live keys.
4. Click **Test Connection** to create a ₹1 Razorpay **sandbox order**, without capturing any money. A success verifies only that the provider accepted the sandbox request; it does not authorize checkout or licensing.
5. Razorpay's **Webhooks** dashboard provides secret setup for signed callbacks. Do not register an invented KMJ webhook URL: the production receiver has not been released/verified yet. Once a dedicated HTTPS endpoint exists and has passed safe sandbox tests, configure its URL and an independently generated webhook secret in the provider dashboard and save the matching secret in KMJ.
6. Account activation / website verification / international card acceptance are *separate* provider approvals. Merchant owner reports approval; no independent API confirmation has been obtained.

Razorpay official references:
- https://razorpay.com/docs/payments/dashboard/account-settings/api-keys/
- https://razorpay.com/docs/payments/dashboard/account-settings/webhooks/
- https://razorpay.com/docs/payments/dashboard/test-live-modes/

### Cashfree

1. Open https://merchant.cashfree.com/merchant/pg#api-key and select **Test / Sandbox** API credentials in the authenticated merchant portal.
2. In KMJ `/operator/payments`, select Cashfree → **Save keys in KMJ**. The credentials are encrypted at rest and never echoed back to the browser.
3. Enter **your authorized sandbox test phone** and click **Test Connection**. The server creates a ₹1 sandbox-only order (no payment capture); use only a test phone you control. It may receive test-provider notifications.
4. A saved Cashfree secret is not a validated webhook event receiver. Keep live charging disabled until signed callbacks and payment capture are independently verified.
5. Treat cross-border payments, card methods, recurring subscriptions, settlement proofs, and currency support as separate merchant-enabled capabilities.

Cashfree references:
- https://www.cashfree.com/docs/payments/overview
- https://www.cashfree.com/devstudio/preview/pg/web/checkout

## Security and acceptance gates

1. Owner login + verified email + recent password confirmation + passkey-backed PlatformOwnerAccess.
2. `payment_gateway_settings` migration present; store test credentials encrypted, use test-only provider credentials; allow rotation and revocation. No secret in Git, frontend bundle, ChatGPT, task prompt or application logs.
3. Verify provider API connectivity in sandbox using real test credentials and an isolated, audited QA environment.
4. Create a server-authoritative commercial order with fixed amount/minor units and currency; verify provider order/merchant account/environment idempotently.
5. Implement provider-specific public HTTPS webhook endpoints with exact raw-body signature verification, event deduplication, atomic append-only ledger, safe retries and verified provider GET capture status.
6. Exercise payment success, pending/failure, duplicate/replay, out-of-order, wrong amount/currency/customer/organization, refund and chargeback. A browser callback alone cannot grant a license.
7. Verify that only a settled and operator-authorized order can result in a KMJ Main Platform signed entitlement and revocable license.
8. Obtain actual provider approval for international processing and confirm tax/invoice/refund/cancellation policy. Verify isolated PostgreSQL migrations and rollback, authenticated browser smoke, exact-head tests, backup + restore proof, and an authorized live canary before any live customer charge.

**Explicitly NOT ready:** one-click collection of live merchant keys, production webhook handling, automatic payment capture, automatic subscription and paid license activation. UI setup is a safe owner configuration workflow only.

**Potential interim B2B sale:** An owner may separately issue a customer-specific **Razorpay Payment Link** in the official merchant dashboard after agreeing scope, invoice/tax terms, refunds and delivery with the customer. That is not an integrated CodeBridge checkout. Verify the payment in the merchant dashboard and manually follow the authoritative commercial order and entitlement process; never let an AI auto-charge buyers.

Relevant code:
- `apps/platform/routes/payments-console.php`
- `apps/platform/app/Services/Payments/OwnerPaymentGatewaySettings.php`
- `apps/platform/app/Services/Payments/PaymentGatewayReadiness.php`
- `apps/platform/resources/js/components/payment-gateway-onboarding.tsx`
- `apps/platform/tests/Feature/OwnerPaymentGatewaySettingsTest.php`
