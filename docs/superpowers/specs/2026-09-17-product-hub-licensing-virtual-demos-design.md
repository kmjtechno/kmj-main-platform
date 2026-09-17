# KMJ Product Hub, Licensing, and Virtual Demo Design

**Date:** 2026-09-17  
**Status:** Approved direction; implementation follows only verified product evidence  
**Primary repository:** `kmjtechno/kmj-main-platform`

## Goal

Turn KMJ Main Platform into the central customer-facing product authority for KMJ software: customers should understand a product in seconds, experience a safe interactive virtual demo, compare verified capabilities, and move into a governed purchase/license flow without misleading claims.

Initial flagship products are `KMJ CloudOS` and `KMJ Calibration Pro`. The catalog architecture must support adding other KMJ repositories later without redesigning the site.

## Evidence baseline

- Main Platform already contains commercial product, organization, entitlement, purchase, audit, sandbox license issue/validate/revoke, and Rust sandbox-verifier foundations.
- The current license verifier is explicitly sandbox-only. Production asymmetric signing/key custody remains owner-gated and code-signing keys stay separate from license-signing keys.
- KMJ Calibration Pro V4 currently identifies itself as a buildable C++ foundation, not a working calibration application. Its master state says the product is incomplete and physical capability remains uncertified.
- KMJ CloudOS contains its own release-gate source of truth. Public claims must be derived from observed evidence, not from roadmap intent alone.

These facts control what the website may say. Marketing presentation must never outrun engineering evidence.
## Product truth model

Every listed product has two separate concerns:

1. **Commercial authority** — the existing Main Platform Product/Entitlement/Licensing chain decides whether an organization may use a product.
2. **Presentation authority** — a curated, testable product-facts record keyed by the same product slug controls public copy, lifecycle state, demos, comparisons, supported platforms, evidence references, and CTA availability.

A public page must not infer capability from a repository name, roadmap, mockup, or AI output. Each factual claim is either backed by repository/runtime evidence or explicitly presented as planned/preview functionality.

Lifecycle states are explicit: `development`, `preview`, `available`, `deprecated`. A product in `development` or `preview` cannot show an unconditional `Buy now` CTA unless the commercial offering itself is verified available.

## Customer experience

### Products hub — `/products`

The page is outcome-first, not specification-first. A visitor gets, at a glance:

- product name and one-sentence outcome;
- lifecycle/availability state;
- three evidence-backed differentiators;
- a real UI capture or deterministic product diagram;
- primary CTA: `Try virtual demo`, `Request demo`, or `Buy license` according to verified availability;
- secondary CTA: `See details`.

The first viewport should explain the value without requiring a long feature list.
### Product detail — `/products/{slug}`

Each detail page follows the same comprehension order:

1. outcome hero;
2. three-to-five verified capability cards;
3. interactive virtual demo;
4. `How it works` workflow;
5. evidence-backed comparison;
6. supported deployment/integration facts;
7. pricing or sales path only when real commercial facts exist;
8. trust/licensing explanation;
9. final CTA.

Technical depth stays below the conversion-critical content so a technical buyer can inspect it without forcing every visitor through it.

## Virtual demos

Virtual demos are deterministic browser experiences, not videos and not fake access to production systems. They must be clearly labelled `Interactive preview` and use seeded sample data.

### KMJ Calibration Pro preview

The preview communicates the intended workflow: connect/configure -> capture pattern -> analyze -> result. Until real hardware/UI evidence exists, the demo must not display fabricated physical accuracy, camera support, calibration PASS, or measured timing. Any sample values are visibly labelled simulated.

### KMJ CloudOS preview

The preview communicates monitor -> validate -> deploy -> verify/rollback using a self-contained simulated environment. It must not call real infrastructure, mutate live deployments, or imply that sample workers/deployments are live customer systems.
## Licensing architecture

KMJ Main Platform remains the central authority for organization -> product -> entitlement -> license decisions. Product repositories consume a narrow verification contract; they do not receive direct database access.

The rollout is staged:

- keep the existing sandbox HMAC lifecycle as the staging/test contract;
- define versioned license claims and deterministic cross-language golden vectors;
- add product-side verification adapters for CloudOS and Calibration Pro;
- fail closed on wrong product, wrong entitlement, expiry, revoked identifier, malformed artifact, or unsupported contract version;
- support bounded offline/grace behavior only where the product requirements explicitly require it;
- add device binding only as a policy capability, not as the sole activation path;
- keep production asymmetric signing material outside application tables and source control.

Production signing/key custody is a separate owner-approved security operation. No implementation task may silently create or store a private production key.

For Calibration Pro, product-side enforcement can be scaffolded and tested against golden vectors before the runtime is complete, but the site must not claim the unfinished application is commercially protected/ready. For CloudOS, integration must follow its actual runtime boundary after repository inspection.

## Comparison policy

The website may compare KMJ products with named or generic alternatives only using current, reproducible facts. Comparison rows should focus on capabilities that buyers can verify: deployment model, supported workflows, offline/self-hosted operation, evidence/audit support, integration surface, licensing model, and published price where available.

No fabricated percentages, star ratings, review counts, customer quotes, market-leader labels, or `world's best/cheapest` claims. When KMJ is objectively stronger on a measured criterion, show the criterion and evidence rather than an unsupported superlative.
## Visual asset policy

Primary visuals come from the products themselves: real screenshots, browser-rendered interface states, deterministic diagrams, verified logs/evidence views, and short recordings captured from real builds.

AI-generated imagery is not the default product evidence and must never impersonate a real screenshot. If a decorative illustration is ever used, it must be visually consistent with the site and clearly separate from factual product evidence.

## Main Platform components

The implementation should introduce focused units rather than expanding `routes/web.php` or one giant page:

- `ProductShowcaseCatalog` — server-side curated presentation facts keyed by canonical product slug;
- product showcase DTO/schema — validates lifecycle, claims, CTA, evidence and demo configuration;
- `ProductsController` — products index/detail routes and availability shaping;
- React product hub and reusable product-detail shell;
- isolated demo components for Calibration Pro and CloudOS;
- comparison component that renders only evidence-approved rows;
- trust/licensing component that explains entitlement and license status without exposing secrets.

The existing commercial Product model remains the authority for what can actually be purchased. Presentation records reference it by slug but cannot create entitlements or grant access.

## Repository integration

`kmjtechno/kmj-main-platform` owns catalog presentation, commerce authority, entitlement authority, license issuance/revocation and public product experience.

`kmjtechno/kmj-calibration-pro` owns its desktop runtime and a thin license-verification adapter. Its roadmap and software/hardware evidence remain authoritative for product capability status.

`kmjtechno/kmj-cloudos` owns its runtime and a thin license-verification adapter. Its release gates/evidence remain authoritative for capability status.

Future KMJ products plug into the same versioned presentation and licensing contracts rather than adding bespoke website logic.
## Testing and acceptance

The first release is accepted only when:

- product index and detail routes render from validated presentation records;
- lifecycle state controls CTA availability and prevents unavailable products from being sold accidentally;
- virtual demos are deterministic, isolated, keyboard accessible, and make zero privileged/live mutations;
- comparison content has explicit evidence references and rejects unsupported claim types;
- Main Platform license tests cover wrong product, wrong organization/entitlement, expiry, revocation, malformed input and version mismatch;
- product-side adapters pass shared golden vectors before they can be marked integrated;
- tenant/capability authorization remains fail-closed;
- existing foundation, platform runtime, architecture and delivery-progress gates stay green;
- staging exact-SHA deployment and authenticated smoke tests pass before any live-site claim changes.

## Delivery order

1. Product truth/presentation schema and evidence policy.
2. Products hub and product-detail shell.
3. Calibration Pro and CloudOS deterministic virtual demos.
4. Evidence-backed comparison blocks and CTA gating.
5. Shared versioned licensing contract/golden vectors.
6. CloudOS product-side verification adapter.
7. Calibration Pro verification adapter/scaffold aligned to its current runtime maturity.
8. Staging integration, browser acceptance, exact-SHA evidence and copy review.

## Non-goals for this stream

- no changes to `kmjtechno.com` production DNS;
- no production private-key creation/custody;
- no fake testimonials, ratings, prices, benchmarks or physical calibration results;
- no live demo that controls customer or KMJ production infrastructure;
- no claim that an unfinished product is generally available;
- no dependency on paid AI or GitHub-hosted runner capacity.

## Success criterion

A new visitor can identify what each KMJ product is for and experience its core workflow within seconds, while every commercial, technical and licensing statement remains traceable to real authority/evidence and the purchase path remains governed by Main Platform entitlements.