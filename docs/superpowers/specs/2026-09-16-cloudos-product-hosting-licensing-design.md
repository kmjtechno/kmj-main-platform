> **SUPERSEDED (2026-09-16):** Do not mirror the legacy `kmjtechno.com` website into staging. `staging.kmjtechno.com` must serve the native KMJ TECHNO Main Platform. The legacy site is reference material only for approved products, services and factual content.

> **OWNER REAFFIRMATION (2026-10-13):** Final production hosting on CloudOS is mandatory, not optional; the owner also locked **Nginx-free Main Platform hosting** (CloudOS-managed Caddy ingress and isolated FrankenPHP classic-mode Laravel runtime) on 2026-10-13. The **hosting/licensing boundaries** below remain applicable; the historical staging-mirror sections and their staging root/legacy-IP implementation details remain **superseded and must not be implemented**. Use [ADR-009](../../adr/ADR-009-main-platform-on-cloudos.md) and [deployment contract v1](../../../contracts/deployment/main-platform-cloudos-v1.json) for active deployment, QA, resilience and cutover direction. Production cutover remains unexecuted.

# KMJ CloudOS Product, Licensing, Hosting and Staging Mirror Design

**Status:** Approved by owner on 2026-09-16.

## Intent

KMJ TECHNO Main Platform is the commercial, customer, entitlement and licensing authority for KMJ CloudOS. KMJ CloudOS remains a separate product/runtime repository and becomes a first-class commercial product in Main Platform. The final Main Platform deployment target is KMJ CloudOS itself.

Until final cutover, `staging.kmjtechno.com` is the temporary production-facing domain: its public website mirrors the current live `kmjtechno.com` experience while defined Main Platform application routes and `/info` remain available for delivery work.

## Authority boundaries

- Main Platform owns customer identity, organizations, product catalog, orders, payment evidence, entitlements, license authority, revocation and commercial audit.
- KMJ CloudOS owns hosting/runtime execution, node/fleet operations, service lifecycle and local enforcement of signed license policy.
- KMJ CloudOS remains in `kmjtechno/kmj-cloudos`; it is not merged into the Main Platform repository.
- CloudOS consumes released Main Platform contracts/APIs; it must never read Main Platform databases directly.
- Payment confirmation is not a license. Explicit entitlement fulfillment remains required before license eligibility.
- Client/runtime state is not final license authority.
- Private signing keys must never be stored in application database rows.

## CloudOS commercial product contract

Canonical Main Platform product facts:

- slug: `kmj-cloudos`
- name: `KMJ CloudOS`
- status: `active`
- entitlement capability: `cloudos.platform.access`
- entitlement policy code: `cloudos.platform.default`

The product must be idempotently synchronized into the catalog by an explicit application command invoked by staging/deployment automation. Re-running synchronization must not create duplicate products or policies and must fail closed if an existing slug/code is bound to conflicting facts.

The existing commercial path stays authoritative:

`Organization -> Purchase Request -> Payment Confirmation -> Explicit Fulfillment -> Entitlement`

CloudOS licensing consumes only an active entitlement for the canonical CloudOS product/capability. Initial implementation establishes product/entitlement/license eligibility and integration boundaries; production signing-key activation remains a separately gated secret operation.

## CloudOS outage and hosting behavior

The CloudOS release contracts require `kmjtechno.com` as the central control hub, separate logical license/fleet/telemetry/update services, offline operation, and continued existing hosting during a central/license outage. The Main Platform/CloudOS integration therefore uses last-known-good signed entitlement plus bounded offline grace on CloudOS; central outage must not terminate existing workloads.

Phase 2 additionally requires the data plane to survive control-plane restart and surviving regions to continue existing workloads. Hosting Main Platform on CloudOS must therefore avoid circular hard dependency: CloudOS can revalidate/renew centrally when connectivity exists, but an already-authorized Main Platform workload remains available through the configured offline grace window.

## Temporary staging homepage mirror

The exact staging homepage `/` and otherwise-unmatched public GET paths use the temporary production-site mirror; defined Main Platform routes always keep priority. On the exact host `staging.kmjtechno.com`, when the staging mirror configuration is enabled, Main Platform fetches the current production homepage from `https://kmjtechno.com/` using the known production origin IP with TLS SNI/hostname validation preserved. A short cache limits origin load and a last-known-good cached copy may be served on transient fetch failure.

The mirrored response:

- returns production homepage HTML only, never production cookies or headers;
- injects `<base href="https://kmjtechno.com/">` so relative links/assets resolve to production;
- injects a staging-only noindex marker and `X-Robots-Tag: noindex, nofollow`;
- exposes a deterministic `kmj-staging-mirror=production-home` marker for deployment QA;
- never mirrors `/info`, `/info/status`, authenticated Main Platform routes, APIs, or operator controls.

Production `kmjtechno.com` is not modified. DNS is not modified. If the mirror is disabled or the request is not the exact staging host, the normal Main Platform home remains available.

## Verification and delivery

- TDD covers staging-host gating, production-host isolation, HTML marker/base injection, successful fetch, cache fallback and fail-closed behavior.
- TDD covers CloudOS catalog sync idempotency, canonical product facts and CloudOS-specific entitlement capability.
- Purchase Center must list CloudOS after catalog sync.
- Staging deploy QA must verify the mirror on `/` and keep progress/operations verification on `/info`.
- Existing authenticated staging smoke remains mandatory.
- Main Platform hosting cutover to CloudOS is a later deployment event and requires owner approval because it changes production infrastructure/DNS.
