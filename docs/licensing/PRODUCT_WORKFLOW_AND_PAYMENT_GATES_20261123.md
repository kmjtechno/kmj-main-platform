# KMJ Licensing Hub — product-aware workflow and payment acceptance matrix

**Date:** 23 November 2026  
**Authority:** `KMJ_TECHNO_MAIN_PLATFORM_MASTER_ROADMAP_BLUEPRINT_V1_0.md`, later approved ADRs and current source/ledger evidence.  
**Status:** Source-review implementation plan; **NOT** production authorization or evidence of actual merchant settlement.

## One authority; distinct user experiences

The Main Platform's KSLP commercial entitlement/licensing record remains the only authority. AuthSP is a **user-workflow reference**, not a second database, credential issuer, API server, checkout backend, or signing root.

1. **Customer:** verified account → organization → catalog + approved offer → server-issued order → customer-authorized provider checkout → verified captured/refunded-state reconciliation → authorized subscription → entitlement → product-specific signed license → attested device activation/renewal → download/support.
2. **Customer organization admin:** membership/team management, assigned seats, subscriptions and invoices, product licenses, device limits and transfer requests; never global license issuance or foreign-tenant visibility.
3. **Developer/issuer (AuthSP-style):** verified and subscribed organization → register applications → product/audience SDK setup → scoped API/key issuance within quota → own activations, renewals, API diagnostics and audit. Subscription to a commercial KMJ product does **not** automatically create an issuer subscription.
4. **KMJ owner:** cross-tenant product/plan approval, merchant setup, refunds, issuer tier approval, reason-bound license lifecycle, signing key references and global audit. Financial/signing/destructive actions require step-up, explicit reason and independent verification.
5. **Support/reseller:** only delegated tenant/seat/issuer scope; no merchant secrets, server private keys, unreviewed price overrides or global admin.

### Owner console information architecture

- **Overview:** product-aware launch/readiness and next action.
- **Customers & licenses:** search customer, inspect entitlements and bound device activations, issue only the verified product profile, renew, revoke or transfer with audit.
- **Developer apps & keys:** AuthSP-inspired apps/SDK/keys/quotas; separate permission boundary.
- **Security & audit:** lifecycle evidence and gated account cleanup (paused until independently approved), not mixed with daily licensing.
- **Payment gateway setup:** separate dedicated console connected to the **same** order/subscription authority. A payment webhook never directly creates a signed license.

## Product registry reconciliation (source defaults, not live merchant claims)

`KmjProductCatalog::syncAll()` registers CloudOS and **14 additional sandbox-product slugs**. Its defaults are applied only to untouched catalog entries; actual operator-edited database state must be rechecked. `purchase_enabled` or `licensing_enabled` is a catalog signal, **not** proof of approved pricing, live payment capability or interoperable signing.

| Product/family | Source default lifecycle | Purchase default | Licensing default | Required product workflow |
| --- | --- | --- | --- | --- |
| KMJ CloudOS | available | yes | yes | Organization entitlement, approved subscription, CloudOS audience, signed lease, online/offline acceptance |
| KMJ OmniDesk | research | no | yes | Account + subscription, seat/device authorization, 2-PC signed lease, renewal/transfer/revoke, native client proof |
| KMJ CodeBridge | research | no | yes | Organization/device pairing, scoped machine identity, subscription/usage policy, short-lived revocable entitlements |
| KMJ Calibration Pro | preview | no | no | Hardware/projector/device policy, compatible offline activation, edition/seat profile, golden test vectors |
| KMJ Forge, KMJ Agent | research | no | no | Future developer product audience, consumption and capabilities profile before checkout |
| KMJ Connect | planned | no | no | User/team collaboration scope and identity/seat model before monetization |
| KMJ Cloud Nexus | research | no | no | Distinct IDE boundary; no shared direct database authorization |
| KMJ Creative Studio | planned | no | no | Creation/export feature rights and usage tier if/when approved |
| KMJ Cinema Platform / 360 Dome / Cinema Player / Immersive Cinema Suite | research / planned | no | no | Per-installation/projector/media-device and offline/industrial policy; quotation/contract-first for custom deployments |
| KMJ Licensing Hub | research | no | yes | Internal commercial authority; **do not create a second paid-licensing authority** |

Additional constants `kmj-ai-support`, `kmj-automate` and `kmj-ai-gateway` are **declared but not inserted** by the current `syncAll()` sandbox product map. CineCore and MotionDirector require an approved canonical-product identifier/profile reconciliation before treating their development repositories as sellable catalog products. Do not silently invent prices, licenses, product IDs or release claims.

## Payment-gateway implementation, in order

**Current implementation evidence (merged main `8df130e8dc35b1872506095da2347b37c2eab88e`):** Razorpay/Cashfree owner sandbox credential vault, provider-specific sandbox order/client probes and signed webhook receipt paths exist in source. Razorpay sandbox durable order-intent and bounded reconciliation were merged through #1074; #1078 added fail-closed order-link environment/INR checks and explicit integer-zero refund evidence. These remain **sandbox-only** and do not prove a real merchant capture, live charging, refunds, entitlements or product-specific signing. The older #928/#929/#1056/#1064/#1068 branches remain audit history; do not merge them again over current main. No source-level test is a merchant settlement receipt.

**Gate 0 — catalog:** For each product/region, owner-approved SKU, plan, price in minor units, currency, term, tax treatment, region eligibility, refund/renewal policy and product-specific signing profile; absent facts = unavailable checkout.

**Gate 1 — provider enrollment:** Razorpay India and Cashfree fallback/cross-border only where merchant-enabled. Owner-controlled dashboard keys remain encrypted on Elite, write-only to frontend, independent test/live modes; no unapproved auto-provider fallback.

**Gate 2 — order lifecycle:** Tenant/user authorization; server-priced quote and order; durable outbound attempt reservation before external HTTP; never repeat an uncertain provider create/capture; amount/currency/merchant/product exact matching and idempotency.

**Gate 3 — payment verification:** Raw-body HMAC verification for each provider, event inbox/dedupe, provider-side GET confirmation of captured/unrefunded funds, correct environment, immutable ledger and pending/unknown/refund/dispute handling. Browser return is not proof.

**Gate 4 — subscription fulfillment:** Idempotent verified order → approved subscription → entitlement policy → protected signer issuance → registered device/seat activation; outage/retry safety, review queue and reversals. No client-shared private signing keys.

**Gate 5 — go-live evidence:** Exact-head CI and PHP/TS/Rust compatibility, isolated PostgreSQL migration/rollback, authorized sandbox provider E2E, refund/chargeback/negative cases, 2-device product validation, authenticated browser QA, backup/restore, owner commercial approval, signed Elite staging→production. No production customer charge prior to gate approval.

### Non-negotiable acceptance cases

- Wrong tenant/user, unknown SKU, unapproved price, swapped product audience, revoked issuer, over-quota app or device → denied server-side.
- Wrong amount/currency/environment/provider account, altered signature, replay, early/late webhook, provider timeout and refund → no premature fulfillment or duplicate charge.
- Safe same-order retry and exact once ledger transition; protected signing service unavailable → pending/retry or owner queue, **not** unsigned activation.
- Expiry, suspension, refund, revoke and transfer propagate to renewable leases; offline grace is bounded and signed.
- Owner, developer, customer, reseller and support see only their allowed activities and tenant data; account cleanup stays blocked until separately approved.

## Connected product repository cross-check (23 November 2026)

Source readmes were inspected in the current accessible GitHub repositories; a README is product guidance, **not** proof of commercial production release.

| Repository | Verified source-level observation | Licensing/payment integration implication |
| --- | --- | --- |
| [kmj-omnidesk](https://github.com/kmjtechno/kmj-omnidesk) | README explicitly describes **pre-alpha**, implemented Rust Ed25519 verification and signed policies; production KMS/signer integration, real-world connectivity campaign and release remain gated | Reuse unique Main Platform OmniDesk product audience and device/seat lease; don't turn on checkout from client-side verification alone |
| [kmj-codebridge](https://github.com/kmjtechno/kmj-codebridge) | Developer-preview bridge with explicit device/project scoping, OAuth and no arbitrary shell; README describes local-model-first workflows | Billed feature rights should target scoped device/project/organization and policy, not expose runtime credentials; the README's local-first AI design differs from the Main Platform roadmap's cloud-only AI-router policy and needs a scoped architecture decision, **not** silent reconciliation |
| [kmj-cloudos](https://github.com/kmjtechno/kmj-cloudos) | Public README is a minimal project description, not live signing/payment evidence | Keep current CloudOS KSLP v1 compatibility and require runtime/signer/device proof before broader claims |
| [KMJ-Calibration-Studio](https://github.com/kmjtechno/KMJ-Calibration-Studio) | Independent Qt6 camera/projector calibration program; source describes working 2D workflow and remaining hardware/feature validation | Treat a calibration license as an industrial workstation/projector installation right, not a browser subscription or web-hosted playback service |
| [kmj-cinecore](https://github.com/kmjtechno/kmj-cinecore) | Active Windows/C++/Qt/D3D12 development; README says actual projection, media and motion hardware evidence is still pending | Canonical catalog alignment and per-site/operator/OEM licensing profile must precede a sellable CineCore checkout |

The earlier `vioso-clone` repo identifier could not be retrieved through the connected GitHub account in this review; do not infer current code or release state from prior notes. Other product families require individual repository/profile verification before commercialization.

## Delivery dependencies

- The reviewed Razorpay SANDBOX reconciliation guards are already merged on main through #1074 and #1078; keep live-merchant enrollment, chargeback/refund subscription ledger and product signing as separate unapproved gates. Do not independently deploy or re-merge obsolete #928/#929/#1056 or the OmniDesk stacked drafts.
- New navigation UX in this branch does not add financial endpoints, issue licenses, mutate DB, or enable cleanup.
- Product-specific authenticated UI/E2E and checkout cannot be marked complete without real merchant and device evidence.
