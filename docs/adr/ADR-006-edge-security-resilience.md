# ADR-006 — Edge, Security & Resilience Refinement

- **Status:** Accepted
- **Owner approval:** 2026-09-12
- **Scope:** KMJ TECHNO Main Platform
- **Does not modify:** KMJ Cloud Nexus

## Context

The canonical Main Platform remains a modular monolith with event-driven seams, provider-neutral adapters, evidence-gated extraction, and explicit production approval boundaries.

This ADR records only the useful edge/security/resilience refinements accepted from the 2026-09-12 architecture review. It does not replace the master roadmap.

## Accepted decisions

### 1. Cloudflare is an edge provider, not application authority

Cloudflare may provide CDN, TLS edge termination, DDoS mitigation, WAF/rate-limit controls, Turnstile, cache management and related edge services.

The application must remain functional without Cloudflare-specific business logic. Provider-specific capabilities stay behind adapters and documented degraded modes.

### 2. Cache only explicitly safe public/read-only surfaces

Static assets and explicitly public/read-only responses may use aggressive edge caching when cache semantics are deterministic and tested.

Authenticated, admin/operator, commerce, entitlement, licensing, activation, audit, privacy and other authority-bearing responses must not use blanket `Cache Everything` behavior.
### 3. R2 is an optional S3-compatible storage provider

Cloudflare R2 may be used for backups, snapshots and suitable media through the existing S3-compatible object-storage interface.

R2 must not become a hard-coded domain dependency. Backup restore remains independently tested.

### 4. Turnstile and edge anti-abuse are targeted controls

Turnstile is recommended for signup, checkout and abuse-prone public forms. Login protection should be risk/adaptive rather than an unconditional usability barrier.

Edge rate limits should protect authentication and high-abuse endpoints. Origin-side authorization, validation and throttling remain mandatory.

### 5. Infrastructure control is governed

The operator console may expose integration health, configuration status, cache purge and other low-risk edge operations.

Production DNS, firewall/WAF policy mutation, certificates, billing-sensitive infrastructure and other material production changes require the existing owner-approval path:

`Plan -> Preview -> Approval -> Execute -> Verify -> Audit`

Kristi or any autonomous worker must not bypass this gate.

### 6. Infrastructure as Code is staged, not a revenue blocker

Terraform/Pulumi-style declarative infrastructure is desirable for reproducibility, beginning with staging and only after the near-term revenue-capable path is not blocked by it.

Production application of IaC remains approval-gated and rollback-aware.
### 7. Security scanning should strengthen PR CI

SAST, dependency vulnerability auditing and secret scanning should be added where they are reliable, deterministic and compatible with repository policy.

Existing architecture tests, authorization tests, contract verification and independent evidence remain required.

## Deferred / not accepted as current architecture

The following are not current commitments and must not be treated as project facts:

- `10M+ concurrent users` or `zero downtime` as achieved capability; these are scale aspirations until benchmarked.
- a mandatory message broker for internal domain events before measured need; transactional outbox comes first.
- per-module physical database/schema credentials everywhere before evidence justifies the operational cost.
- blanket edge caching of dynamic or authority-bearing APIs.
- unrestricted automatic DNS/WAF/firewall provisioning from the admin panel.
- mandatory Pact/schema-registry infrastructure when current OpenAPI/CloudEvents contract verification is sufficient.
- universal Zod/TypeBox use across PHP boundaries.
- microservice extraction, Kubernetes, NATS or specialist runtimes without measured bottlenecks.
- chaos/DDoS testing against production; resilience testing belongs in controlled environments.

## Implementation order

This ADR must not interrupt the canonical near-term roadmap. Current priority remains the revenue-capable authority/licensing/commerce path. Edge hardening is introduced incrementally when it reduces verified risk or origin load without delaying that path.

Any material extension of this ADR requires measured evidence, rollback design, independent verification and a new/updated ADR.