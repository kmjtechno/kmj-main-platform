# KMJ OmniDesk — India Freemium Launch Pricing (Owner-Directed Draft)

**Reference date:** 2026-11-23. **Offer version:** `2026-11-23-INR-v1`. **Source authority:** `OmniDeskOfferCatalog` in the *existing* Main Platform KSLP Licensing Hub. This document is NOT a claim that any remote-control capability or commercial payment flow is live.

## Competitor anchors — official pages, verified 23 Nov 2026

| Service | Public example | Important comparison caveat |
| --- | --- | --- |
| AnyDesk | Solo **$23.12/month equivalent promotional** (regular $28.90) | Paid **annually**; not $23.12 monthly collection, region/offer varies |
| Splashtop Remote Access | Solo **$72/year**, **$6/month equivalent** | Remote Access Solo yearly commitment; official Solo increase effective 1 Mar 2026 |
| Zoho Assist | Remote Support Standard **$10/technician/month equivalent** | Billed annually in the official USD annual offer; product seat model differs |
| RustDesk | Free self-hosted edition; Individual Server Pro sold separately | **Self-hosted**, customer bears hosting/ops expense |

Source URLs:
- https://anydesk.com/en/pricing
- https://support.anydesk.com/docs/do-you-offer-monthly-subscriptions-or-payments
- https://www.splashtop.com/pricing
- https://support-splashtopbusiness.splashtop.com/hc/en-us/articles/44904971068955-Frequently-Asked-Questions-Solo-Price-Increase
- https://www.zoho.com/assist/pricing.html
- https://rustdesk.com/pricing/

These competitor SKUs are not feature-equivalent. Do NOT claim lowest price globally or identical uptime, security, operating systems or device quotas.

## Recommended launch price book — INR before applicable taxes

| Plan | Monthly contract total | Annual contract total | Licensed users | Managed devices | Concurrent sessions | Unattended devices | Monthly relay cap |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Personal Free | ₹0 | ₹0 | 1 | 1 | 1 | 0 | 0 GiB; direct-only |
| 14-Day Business Trial | ₹0 | None | 2 | 10 | 1 | 5 | 1 GiB |
| Professional | ₹149 | ₹1,490 | 1 | 3 | 1 | 2 | 2 GiB |
| Business | ₹499 | ₹4,990 | 5 | 25 | 2 | 15 | 20 GiB |
| Enterprise | ₹1,499 | ₹14,990 | 20 | 100 | 5 | 75 | 100 GiB |
| Custom/OEM | Quote | Quote | Agreed | Agreed | Agreed | Agreed | Quoted |

**Annual discount = two months free** relative to twelve monthly payments: 12 × ₹149 = ₹1,788 versus ₹1,490, 12 × ₹499 = ₹5,988 versus ₹4,990, 12 × ₹1,499 = ₹17,988 versus ₹14,990. Yearly subscription amounts are **upfront**; never present annual/12 as a monthly bill. Do NOT describe the plan limits as working native client functionality until two-PC release tests prove enforcement.

**Monthly relays are limited intentionally**: direct P2P preferred, keep relay budgets bounded; no promise of unlimited data or guaranteed direct NAT traversal. For a small-spend offer this reduces exposure to bandwidth abuse. Personal Free prohibits commercial use, unattended access, relay bytes and file transfer.

## Acquisition and conversion — useful, not manipulative

1. Clearly offer free personal (when the security-gated native workflow is actually available), or a one-time 14-day trial from a verified Main Platform account **without asking for a card**. Trial never silently turns into a paid mandate. One trial per organization and trusted device identity; independent native proof still required.
2. First-session onboarding: invite one permitted device, verify customer consent, establish *attended* connection, explicitly confirm encryption/authentication, and only then show transfer/unattended features when available and authorized. Don't claim AnyDesk parity when those features are unverified.
3. Helpful lifecycle notices: day 3 onboarding assistance, day 10 trial value recap, day 12 expiry reminder, day 14 free/purchase options. Opt out of promotional messaging; transactional expiry notices can remain. Never use countdown manipulation, fake urgency, or punitive data lock-in.
4. Show the customer's actual seat count, concurrent sessions, relay usage and trial expiry (only if telemetry/ledger is authoritative), then the **most relevant** tier. Upgrade path is transparent about amounts, tax and *annual paid upfront* discount. Paid upgrades only after real PSP-verified settlement and entitled period policy.
5. Annual plans reduce transaction frequency and improve realized revenue; Business differentiates by teams/devices. A referral credit mechanism can be reviewed later **only after** anti-abuse, verified settlement, tax and refund rules exist; do not add unrestricted coupons or duplicate trials.
6. Track (aggregated, consent-respecting) time-to-first-attended-session, days active, 7-day cohort retention, real conversion, refund rate, relay cost per active org and payment authorization success. No sale forecasts or simulated success counts in production reporting.

## Gateway and operating economics

Razorpay's official India pricing describes **2% gateway platform fee** on typical successful payments, no setup fee or annual maintenance, and applicable GST on payment processing: https://razorpay.com/pricing/?preferred-country=IN . Real fee schedules can vary by provider/payment method/merchant agreement; verify contract before showing net revenue. A ₹149 monthly base fee at 2% would be ₹2.98 before GST on processing, *not* ₹149 net profit. Bandwidth, support, taxes, fraud, refunds, software maintenance and seat utilization are additional costs; free personal must not consume unbounded relay capacity.

Main Platform already has encrypted **sandbox-only** owner gateway settings, test-key validation, a signed webhook inbox and provider GET proof in the sandbox lane. The production LIVE Razorpay verifier in Draft PR #1075 remains intentionally unbound; it is NOT legitimate to accept payment based on browser callback, manual confirmed commerce row or replayed sandbox evidence.

**Owner must confirm provider onboarding, merchant KYC, live payment methods, GST/invoice rules, refund/cancellation terms and exact signed native Windows release before any paid checkout or trial-enabled remote operation.**

## Source and release policy

- `OmniDeskOfferCatalog::prepare()` adds nine **PAUSED** plans. It NEVER enables product sale, trial self-service, personal free issuer, signing, live capture, renewal, direct/relay network service or KSLP device activation. Existing plans conflict on owner-approved price/limits; no silent overwrite.
- The ONE Super Admin KSLP Hub provides an owner-step-up/CSRF-gated prepare action; the customer Purchase Center renders truthfully labelled unavailable offers until the licensing and payment gates are actually verified.
- OmniDesk trial and paid entitlements are **not equivalent to signed remote-access permission**. The existing trial/paid model requires separate signer, device proof and subscription extension/renewal. No second AuthSP backend.
- GitHub draft CI PASS is source-only verification. Elite-only signing and guarded staging→production promotion require exact approved SHA, backup/rollback and resolved staging drift.

## Owner next decision checklist

- [ ] Confirm proposed India prices and contractual seat limits against support/relay cost evidence.
- [ ] Verify approved merchant LIVE onboarding and supported checkout/mandate/payment methods.
- [ ] Approve first-party product launch status and free/trial policies after secure native pilot.
- [ ] Bind tested provider live settlement/refund/revocation and enforce exact plan/quota in lease.
- [ ] Complete native two-PC signed activation/renewal acceptance and protected Elite release.
