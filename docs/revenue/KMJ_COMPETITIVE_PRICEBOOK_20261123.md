# KMJ TECHNO — Competitive launch pricing and revenue gates

**Research date:** 23 November 2026  
**State:** OWNER-ONLY REVIEW DRAFT. Do not interpret this document, the accompanying JSON, or a successful CI run as permission to charge customers, publish price offers, sign product licenses, change existing subscriptions, or run refunds.

## Canonical product mapping

A single central KSLP authority owns plans, orders, subscriptions, entitlements and product-specific signed leases. The proposed price book is `apps/platform/resources/private/kmj-commercial-pricebook-20261123.json`. Its 15 entries map exactly to `KmjProductCatalog`'s current CloudOS + 14 sandbox product slugs. Four additional entries are **unregistered** roadmap ideas and are not product SKUs. No plan is inserted into the live PostgreSQL `plans` table by this change.

### India launch price candidates

Figures below are **INR before any applicable tax**. Monthly/annual prices do **not** include customer cloud resources, paid AI usage, unmetered relay traffic, hardware, travel, custom installation or bespoke support. Each source-default lifecycle remains unchanged.

| Canonical product | Entry-level draft | Annual draft | Model and gate |
| --- | ---: | ---: | --- |
| KMJ CodeBridge | **₹299/month** | **₹2,499/year** | Existing **13 Nov owner-approved reference**, NOT new pricing; Community free, Team ₹699/user/month minimum 3. Current production sale still disabled |
| KMJ OmniDesk | ₹149/month | ₹1,490/year | Solo 1-user trial target; free personal tier; Pro ₹299/month, Team ₹399/user/month minimum 3; before selling prove signed seats and relay economics |
| KMJ CloudOS | ₹499/month | ₹4,990/year | Professional organization control-plane BYO-infrastructure; Business ₹1,499/month; **not** a hosted VPS/VM package |
| KMJ Forge | ₹199/month | ₹1,990/year | Research only; no bundled paid model inference |
| KMJ Connect | ₹99/seat/month | ₹990/seat/year | Planned; minimum 3 team seats |
| KMJ Cloud Nexus | ₹299/month | ₹2,990/year | Research; user supplies infrastructure and paid AI |
| KMJ Agent | ₹149/month | ₹1,490/year | Research; paid AI/provider usage excluded |
| KMJ Creative Studio | ₹199/month | ₹1,990/year | Planned; media AI/render/storage usage excluded |
| KMJ Calibration Pro | ₹9,999 indicative | — | **Site pilot only, quote required**; not a public per-projector license; hardware acceptance and rights review pending |
| KMJ Cinema Player | ₹4,999 indicative | — | Site pilot, quote required, not yet commercially released |
| KMJ 360 Dome | ₹14,999 indicative | — | Site pilot, quote required; excludes projector hardware and onsite deployment |
| KMJ Cinema Platform | ₹19,999 indicative | — | Site pilot, quote required, separate safety/performance acceptance |
| KMJ Immersive Cinema Suite | ₹39,999 indicative | — | OEM/site pilot, quote required, no advertised public price |
| KMJ Licensing Hub | Not priced | — | Internal authority; third-party issuer SaaS cannot become a second independent licensing root |

**Bundle candidate:** CodeBridge Pro + OmniDesk Solo: ₹359/month or ₹3,190/year, roughly 20% below ₹448/month or ₹3,989/year à-la-carte. Bundle requires two independent signed entitlements, a versioned order/plan and a verified support and transfer policy. Do **not** create a universal entitlement that bypasses product audiences.

Roadmap-only, *not yet catalog registered*: KMJ AI Support ₹299/month, KMJ Automate ₹199/month, KMJ AI Gateway ₹299/month, each with capped/externally supplied model usage; KMJ CineCore quote-only per-site product mapping, not a sellable SKU.

## Direct market anchors — official pages checked 23 Nov 2026

| Market | Official price observed | Important comparison limit |
| --- | --- | --- |
| AnyDesk remote access | Solo US$23.12/month, Standard US$39.92/month, **both billed annually** and page shows a 20% offer | Different concurrency, managed-device caps, and product maturity: https://anydesk.com/en/pricing |
| Splashtop remote access | Solo US$6/month (US$72/year), Pro US$8.25/user/month (US$99/year) | Different remote-access features and delivery: https://www.splashtop.com/pricing |
| RustDesk self-hosted | Free US$0; Individual US$11.88/month annually; Basic US$23.88/month annually | **Self-hosted, not SaaS**. Cannot say KMJ is cheaper than free: https://rustdesk.com/pricing/ |
| DigitalOcean cloud VM | Basic 512 MiB US$4/month, 1 GiB US$6/month, 2 GiB US$12/month | Compute included in Droplet fee; KMJ CloudOS quote above **excludes compute** and is not the same product: https://www.digitalocean.com/pricing/droplets |
| n8n Cloud workflows | Starter €20/month when billed annually (2,500 workflow runs); free self-hosting Community Edition | KMJ automation must specify completed executions and model/infra costs: https://n8n.io/pricing/ |
| AI developer tooling | Cursor current site: Plus US$8/month, Premium US$30/month, third-party AI usage billed separately | Not equivalent to a device-bridge tool; avoid claiming same AI entitlements: https://cursor.com/pricing |
| Projection mapping | Resolume Arena offers multi-projector mapping/edge blending, pricing depends on licenses | Hardware/projector installation and operator training matter more than a universal seat price: https://resolume.com/software/avenue-arena |
| Commercial licensing APIs | Keygen offers free self-hosted CE and metered hosted licensing | KMJ Licensing Hub remains the **internal authority**; no unsupported cheapest claims: https://keygen.sh/pricing/ |

## Growth and margin strategy

1. **Acquisition:** Useful Free/Community tier with truthful limits, no card and no automatically activated paid trial. 14-day opt-in Pro evaluation only after tested entitlement lifecycle. Paid desktop/native application is not released from an untested free trial.
2. **Conversion:** Clear one-person price; annual discount for predictable cash flow; customer controls renewal and cancellation; no misleading countdowns or unexpected renewal. Existing CodeBridge annual prices are locked as already documented; new options are prospective drafts.
3. **Expansion:** Charge for distinct devices, seats, projects or concurrent connections, not arbitrary marketing feature locks; team minimums and enterprise quote. No unlimited relay/AI/storage at ₹99.
4. **Bundle:** Approximately 20% off CodeBridge + OmniDesk if both can be delivered; do not double-count revenue or issue licenses from one unverified coupon.
5. **Professional AV:** Quote-based paid pilot and onboarding per site/projector. Cheap end-user pricing does not cover equipment, technician travel, support, OEM integration or motion safety.
6. **Retain gross margin:** Target >=70% variable gross margin **after** actual processing fees, refunds and recurring variable support/relay/inference cost. Illustrative stress assumptions: 3.5% gateway-fee buffer (including related gateway-tax exposure), 5% refund/dispute reserve, and product-specific measured support/infrastructure cost. These are **planning parameters**, not verified merchant contract rates. The 70% floor is a target, not a forecast or an authorized price.
7. **Zero added fixed cost:** Reuse existing Elite hosting; third-party inference, customer cloud infrastructure, heavy relay and media compute cannot be subsidized silently.

### Payment provider research and offer caution

Razorpay lists a standard 2% platform fee plus GST for many domestic payments. Cashfree lists 1.95% + applicable taxes after eligibility-limited promotional offers. Do not assume a new-merchant promotion applies to the owner's existing approved merchant account; evaluate actual dashboard agreement and per-method effective fee. Sources: https://razorpay.com/pricing/ and https://www.cashfree.com/payment-gateway-charges/.

## Implementation gates before any paid release

1. **Catalog approval:** immutable SKU/version and signed commercial owner decision; amount in minor units, currency, term, tax policy, quantity, country, device/seat cap, price effective window. New version must not retroactively overwrite an existing subscriber's price or already-paid invoice.
2. **Order and subscription ledger:** server-derived price only; user/tenant capability, idempotency, approved product release state and explicit customer purchase consent. Separate trial from paid renewal. State transitions `draft → awaiting_payment → captured_verified → subscribed → entitlement_pending → active`; chargeback/refund/cancel transitions append-only.
3. **Payment providers:** Verify merchant live capability, actual test/live credential custody, server-created order and provider account, raw HMAC webhooks, provider GET for captured/unrefunded status, amount/currency/account/environment. Unknown/early/duplicate events wait/reconcile safely; no blind provider retry. Razorpay sandbox PR #1056 is **not** the live version.
4. **Refunds and reversals:** operator authorized refund to original method, original charge and max refundable amount, idempotent provider refund ID, pending/succeeded/failed status from authenticated provider evidence; chargeback/dispute tracking, subscription adjustment and revocation of future leases. No auto-refund or payout based on a browser response or generated instruction.
5. **License signing:** confirmed commercial entitlement → product-specific verifier contract → isolated trusted signer, key rotation, expiration/renewal and revocation. CloudOS v1 audience cannot be silently used for OmniDesk/Calibration/CineCore. Device/seat transfer and cross-language positive and negative vectors are mandatory.
6. **Protected release:** owner and finance review, legal/tax/refund notice, staging isolated DB+credentials, schema migration/rollback, independent QA, 2-machine client tests, verified backup/restore, signed Elite promotion, observed production canary. Stage and commercial go-live require distinct auditable approvals.

## Revenue illustration (not a forecast)

If a future, fully activated, consented month had 100 CodeBridge Pro monthly subscribers, 100 OmniDesk Solo monthly subscribers and 30 CodeBridge Team monthly seats: gross recurring **₹65,770/month** before GST, processing fees, refunds, usage and support. Counts and retention have **no observed evidence**, so use only for scenario planning.

The draft JSON/owner preview adds **zero** charges, invoices, backend priced orders, active plans or signed leases. No price file may be used directly to calculate a payment-provider order without the reviewed immutable database subscription/offer authority.
