# KMJ TECHNO MAIN PLATFORM
## MASTER ROADMAP & BLUEPRINT — V1.0

**Company:** KMJ TECHNO  
**Project:** KMJ TECHNO Main Platform  
**Primary public domain:** `kmjtechno.com`  
**Canonical GitHub repository:** `kmjtechno/kmj-main-platform`  
**Repository visibility:** Private  
**Canonical branch:** `main`  
**Document status:** **MASTER / CANONICAL ROADMAP BLUEPRINT**  
**Prepared for:** Narendra Singh Kushwah / KMJ TECHNO  
**Blueprint research cut-off:** 9 September 2026  
**Live implementation snapshot:** 10 September 2026  
**Document version:** V1.0  
**Change rule:** Architecture or scope changes must be recorded through an ADR / issue / reviewed change before this document is superseded.

> **LOCKED OWNER DECISION — 13 OCT 2026 — DEPLOYMENT TARGET:** The final Main Platform production hosting and deployment substrate is **KMJ CloudOS**; the Main Platform web service uses **FrankenPHP classic mode behind CloudOS-managed Caddy ingress (Nginx-free)**, rather than Nginx or a PHP-FPM web-serving chain. Main Platform remains the separate business/customer/commerce/entitlement/licensing authority, while CloudOS supplies isolated Linux execution, networking, storage, backups and runtime operations. The repositories remain separate and integrate through versioned contracts; CloudOS must continue already-authorized hosting during Main Platform/control-plane outages. Canonical implementation ADR: [ADR-009](docs/adr/ADR-009-main-platform-on-cloudos.md); synchronized machine-readable contract: [main-platform-cloudos-v1.json](contracts/deployment/main-platform-cloudos-v1.json). This target is **not** a claim that production migration has happened. Keep current production routing/data untouched until staged gates, rollback and owner-approved cutover pass. The superseded legacy staging-homepage mirror must not be revived.

> **LOCKED HYPERSPEED SCOPE — 13 OCT 2026:** CloudOS owns performance, load-balancing and scale-out for Main Platform. Ten-million concurrent users is an aspirational capacity target, **not a verified fact**. Nginx-free Caddy/FrankenPHP; shared Redis/Valkey state; edge-safe public assets, absolutely no shared caching for auth/payment/licensing; real measured RPS, DB/queue caps, failover and finite approved infrastructure budget required. [Performance contract](contracts/performance/main-platform-hyperspeed-v1.json) and [implementation plan](docs/performance/CLOUDOS_HYPERSPEED_PLAN.md). Never claim infinite traffic or zero latency without evidence.

---

# 0. OWNER SUMMARY — HINDI

यह project केवल एक website बनाने का project नहीं है। इसका लक्ष्य **KMJ TECHNO का central digital operating platform** बनाना है, जो भविष्य में company की public website, customer accounts, organizations, subscriptions, entitlements, licensing, devices, releases, downloads, documentation, support, automation, security, audit, Kristi और multiple KMJ products को एक governed system में जोड़ सके।

Main Platform का काम business authority बनना है।  
**KMJ Cloud Nexus अलग engineering IDE रहेगा** और बाद में versioned APIs/contracts के माध्यम से Main Platform से integrate होगा। उसे Main Platform में merge नहीं करना है।

हमारा पहला critical proof यह रहेगा:

`Organization → Product → Entitlement → Signed Sandbox License → Product Validation → Revocation`

अगर यह vertical slice सही, secure और testable बन जाता है, तो उसके ऊपर future products, subscription, licensing, customer portal, Kristi automation और public website को safely expand किया जा सकता है।

इस project की development date-based promise पर नहीं चलेगी। हर phase तभी आगे बढ़ेगा जब उसका **evidence-based exit gate PASS** होगा।

सबसे महत्वपूर्ण locked rules:

- Local LLM inference नहीं।
- Paid AI fallback नहीं।
- Unknown price को free नहीं मानना।
- No verified free route होने पर `NO_FREE_ROUTE_AVAILABLE`.
- Production publish, DNS, billing, destructive DB, signing-key operations बिना explicit owner approval नहीं।
- Payment status = license नहीं।
- Client software final authority नहीं होगा।
- Private signing key application database में नहीं रहेगा।
- One authoritative writer.
- Important PASS claims independently verify होंगे।
- Cloud Nexus इस Main Platform development stream में untouched रहेगा जब तक Phase 6 integration शुरू न हो।
- “Unbreakable / cannot crack” जैसी engineering guarantee नहीं करनी; target layered security, revocation, audit, recovery और verifiable releases है।

---

# 1. DOCUMENT AUTHORITY AND SOURCE HIERARCHY

This file is intended to be the **single saved master roadmap** for future continuation.

When future chats, developers, agents or tools encounter conflicting instructions, use this order:

1. **LOCKED — This master blueprint and later explicit owner decisions**
2. **LOCKED — `KMJ_TECHNO_Platform_Blueprint.docx`**
3. **LIVE — Current `kmjtechno/kmj-main-platform` repository state**
4. **ACCEPTED ADRs / contracts / tests in the repository**
5. **CANDIDATE — Older handoffs and broader Gemini/brainstorm documents**
6. **REJECT / REWRITE — Claims that are impossible, unverifiable, legally unsafe, stale, or contradictory**

Older documents may contain valuable ideas, but they do not override this blueprint when they conflict with the clean-rebuild decision, system boundaries, security model or verified implementation state.

---

# 2. EXECUTIVE DECISION — LOCKED

## 2.1 Core decision

Build `kmjtechno.com` again from a **clean foundation** in a new private repository and staging environment.

The current public site remains untouched until the replacement passes:

- migration gates
- security gates
- reliability gates
- accessibility gates
- SEO gates
- product compatibility gates
- owner approval

The existing site is a **migration input and rollback target**, not a source-code constraint.

## 2.2 What is being built

The Main Platform is the central business/product/customer/licensing/release/automation/intelligence system for KMJ TECHNO.

It will eventually power:

- corporate public website
- product catalog
- customer accounts
- organizations and teams
- orders and subscriptions
- entitlement policy
- licensing and device activation
- product releases and downloads
- documentation
- developer/partner portal
- support and trust center
- content workflow
- privacy requests
- operator console
- Kristi operating layer
- audit and approvals
- AI routing and deterministic automation
- observability and recovery
- integrations with independent KMJ products

---

# 3. SYSTEM BOUNDARIES — NON-NEGOTIABLE

| System | Correct role | Must NOT become |
|---|---|---|
| **KMJ TECHNO Main Platform** | Central business, product, customer, licensing, release, automation and intelligence authority | A thin brochure site or an unrestricted agent shell |
| **KMJ Cloud Nexus** | Separate Code-OSS-based autonomous engineering IDE that develops/operates the Main Platform through released contracts | The website platform, shared database, or hidden Main Platform backend |
| **Kristi** | Governed multilingual operating layer using approved tools, policy, verification and audit | Unrestricted superuser or omnipotent bot |
| **KMJ Product Plane** | Independent SaaS/desktop/mobile/industrial products consuming central identity, entitlement, licensing, update and support contracts | Direct database clients |

### Hard boundary

**Do not collapse Main Platform and Cloud Nexus.**

Cloud Nexus integration belongs later under **Phase 6 — Product Integration**, using versioned APIs, SDKs and events.

---

# 4. PRODUCT OPERATING MODEL

The website is only one experience surface over a larger operating platform.

## 4.1 Experience surfaces

### Public digital experience
For prospects, customers, partners, search engines and AI answer engines.

Includes:

- Company
- Capabilities
- Products
- Industries/use cases
- Research and Insights
- Trust Center
- Developers
- Documentation
- Support
- Careers
- Newsroom
- Contact
- Multilingual content
- SEO / structured data

### Customer and organization portal
For customers and enterprise administrators.

Includes:

- accounts
- organizations
- teams
- subscriptions
- entitlements
- licenses
- devices
- activations
- downloads
- release history
- invoices/order references
- support
- profile and sessions
- privacy/export/deletion requests

### Developer and partner portal
For developers, integrators, resellers and technical partners.

Includes:

- API clients
- SDKs
- webhooks
- sandboxes
- credentials
- usage
- release notes
- partner assets
- integration docs

### Operator console
For governed KMJ internal administration.

Eventually manages:

- customers
- organizations
- products
- plans
- subscriptions
- entitlements
- licenses
- devices
- activations
- orders
- releases
- downloads
- content
- SEO
- automation
- audit
- system health
- security events
- support
- approvals

### Kristi operations plane
For approved autonomous/semi-autonomous workflows.

Closed loop:

`Intent/Planner → Approved Context → Policy Gate → Executor → Independent Verifier → Audit/Notifier`

---

# 5. CANONICAL AUTHORITY CHAIN

This is one of the most important system rules:

`Account → Organization → Subscription → Entitlement → License → Device Activation`

## 5.1 Truth rules

- Payment state is **not** a license.
- A raw payment webhook is **not** the commercial agreement.
- UI visibility is **not** an entitlement.
- A locally editable file is **not** a device right.
- A filename or download URL is **not** a trusted release.
- A generative model output is **not** a public factual claim.

## 5.2 Systems of record

| Fact | Authority |
|---|---|
| Person/authentication | Identity module / identity provider |
| Organization membership | Organizations/IAM |
| Commercial agreement | Order/subscription ledger |
| Permitted capability | Entitlement policy result |
| Device right | License/activation ledger |
| Trusted release | Signed artifact + provenance registry |
| Public factual claim | Approved catalog/content fact |

Product clients never receive direct database access.

---

# 6. ARCHITECTURAL STYLE — LOCKED

## 6.1 Day-one architecture

**Modular monolith + event-driven seams**

Do not begin with dozens of microservices.

Reasons:

- lower deployment complexity
- lower operating cost
- faster business delivery
- simpler transactions
- easier testability
- fewer distributed failure modes
- easier early-stage observability
- easier evolution

Each module still owns its data and contracts so high-load or security-sensitive workloads can be extracted later.

## 6.2 Initial deployment shape

One main application deployment plus separate infrastructure services.

Architecture bands:

1. Global edge
2. Experience
3. Application core
4. Automation and AI
5. Data and integration
6. Trust and operations

---

# 7. VERIFIED TECHNOLOGY BASELINE

## 7.1 Main runtime

### Business/control plane
- Laravel 13
- PHP 8.5 target

### Authenticated UX
- Inertia 3
- React 19
- TypeScript

### Public pages
- Server-rendered Laravel views and/or SSR
- Selective interactive islands where justified

### Primary authority database
- PostgreSQL 18 target
- Row-level security as defense-in-depth
- Logical replication/CDC only for justified migration/analytics use

### Cache, locks, queue support
- Valkey or Redis-compatible service

### Native licensing verifier
- Rust

### High-concurrency bounded services
- Go or Rust only when measurement justifies extraction

### ML/data science
- Python only when actual ML/data science is required
- Never duplicate ordinary business/domain logic in Python

### Object storage
- S3-compatible encrypted object storage

### Observability
- OpenTelemetry

## 7.2 Optional technologies — defer until justified

Do not add these because they are fashionable:

- Laravel Octane
- Temporal
- NATS JetStream
- Kubernetes
- pgvector

Adopt only when measured requirements justify them.

---

# 8. LIVE IMPLEMENTATION SNAPSHOT — 10 SEP 2026

## 8.1 Repository

- Repository: `kmjtechno/kmj-main-platform`
- Visibility: **Private**
- Default branch: `main`
- Current verified `main` commit at snapshot:
  `aff6596ab239fc72be14aa5d717ec00708401303`

## 8.2 Completed and merged

### Foundation / P0-P1 architecture
Completed:
- system boundary ADRs
- modular monolith decision
- commercial authority chain
- verified-zero AI policy
- Kristi governance
- first vertical-slice definition
- CODEOWNERS
- architecture/module boundaries
- CI foundation

### P1-02
**Architecture tests and module skeletons — DONE**

CI enforces:
- dependency cycles
- undeclared module dependencies
- cross-module persistence/model import restrictions
- provider-specific domain coupling
- Cloud Nexus implementation coupling

### P1-03
**Versioned API and event contracts — DONE**

Implemented:
- OpenAPI 3.1 boundary
- Organizations
- Catalog
- Entitlements
- Licensing
- Releases
- CloudEvents-compatible event schemas
- deterministic contract verification

### P1-04
**Application runtime bootstrap — DONE**

Implemented and tested:
- Laravel 13
- PHP 8.5 CI target
- Inertia 3
- React 19
- TypeScript
- PostgreSQL application target
- deterministic SQLite CI-only test database
- pinned official Laravel React starter provenance
- frontend build
- lint
- TypeScript checks
- PHPStan
- PHPUnit

## 8.3 Current active business branch

Branch:

`slice/authority-core-v1`

At this document snapshot it is **8 commits ahead of `main`**.

Files already added include:

- `packages/domain-organizations/composer.json`
- `packages/domain-organizations/database/migrations/2026_09_10_000100_create_organizations_tables.php`
- `packages/domain-organizations/src/Models/Organization.php`
- `packages/domain-organizations/src/Models/OrganizationMembership.php`
- `packages/domain-organizations/src/OrganizationsServiceProvider.php`
- `packages/domain-organizations/src/Services/OrganizationCreator.php`
- `packages/domain-catalog/composer.json`
- `packages/domain-catalog/src/CatalogServiceProvider.php`

Current active goal:

**Authority Slice A — Organization → Product → Entitlement**

After A passes CI, build:

**Authority Slice B — Signed sandbox license → Rust validation → Revocation**

## 8.4 Current known blocker

`main` branch is currently **not protected**.

This means P1-01 cannot be called fully complete until repository protection/ruleset is enabled.

Target protection:

- Require pull request before merge
- Require status checks
- Block force pushes
- Block branch deletion
- Avoid routine administrator bypass
- Preserve CODEOWNERS review path for sensitive changes
- Require branch freshness/up-to-date checks where supported

Tracking issue:

**P1-01: Enable main branch protection / ruleset**

This is an owner-side repository setting unless a write-capable GitHub administration integration becomes available.

---

# 9. DOMAIN MODULES

Initial logical modules:

## 9.1 Identity & Access
Owns:

- users
- credentials
- sessions
- passkeys
- recovery
- service principals
- MFA/2FA state

Events:

- `IdentityVerified`
- `SessionRevoked`

## 9.2 Organizations
Owns:

- tenants
- memberships
- roles
- invitations
- organization profile
- enterprise membership lifecycle

Events:

- `MemberAdded`
- `RoleChanged`

## 9.3 Catalog
Owns:

- products
- editions
- plans
- capabilities
- regions
- lifecycle status
- public product facts

Events:

- `ProductVersioned`
- `PlanPublished`

## 9.4 Commerce
Owns:

- orders
- subscriptions
- invoice references
- payment-provider adapters
- commercial ledger

Events:

- `SubscriptionActivated`
- `SubscriptionSuspended`

## 9.5 Entitlements
Owns:

- grants
- limits
- policy inputs
- effective rights
- terms
- feature rights
- version/channel eligibility

Events:

- `EntitlementGranted`
- `EntitlementRevoked`

## 9.6 Licensing
Owns:

- license records
- device bindings
- renewable leases
- activation records
- revocations
- signing-key metadata references

Events:

- `LeaseIssued`
- `DeviceRevoked`

## 9.7 Releases
Owns:

- channels
- artifacts
- manifests
- rollout rings
- version compatibility
- release status
- rollback metadata

Events:

- `ReleasePromoted`
- `ReleaseRolledBack`

## 9.8 Content & Growth
Owns:

- pages
- locales
- structured data
- redirects
- approval workflow
- content revisions

Events:

- `ContentPublished`
- `RedirectCreated`

## 9.9 Support & Trust
Owns:

- support cases
- security advisories
- incidents
- service/status records
- responsible disclosure workflow

Events:

- `CaseEscalated`
- `AdvisoryPublished`

## 9.10 Automation & Audit
Owns:

- workflows
- approval records
- tool evidence
- action records
- immutable audit trail

Events:

- `ActionApproved`
- `ActionRejected`

---

# 10. DATA ARCHITECTURE RULES

## 10.1 Ownership

Every table belongs to one module.

Cross-module writes happen through:

- application interfaces
- commands/services
- versioned events

Never through ad-hoc cross-module SQL.

## 10.2 Tenant isolation

Tenant-owned rows carry:

`organization_id`

Protection must use both:

- application authorization
- PostgreSQL RLS

RLS reinforces application authorization; it does not replace it.

## 10.3 Append-only ledgers

Use append-only transitions for:

- subscriptions
- entitlements
- licensing
- security
- approvals
- audit

Current derived state should be rebuildable where practical.

## 10.4 Transactional outbox

Domain state and outbound event are recorded atomically.

Consumers must:

- be idempotent
- deduplicate by event ID
- tolerate retry
- preserve ordering only where required

## 10.5 Sensitive data

Classify separately:

- PII
- secrets
- payment tokens
- telemetry
- audit/security data

Analytics and AI do not query production authority tables directly.

They consume minimized, policy-approved projections.

---

# 11. IDENTITY, AUTHORIZATION AND TENANT MODEL

## 11.1 Human users

Preferred:

- Passkeys / WebAuthn
- secure verified recovery
- step-up auth for critical actions

Authorization:

- organization role
- fine-grained capability
- resource ownership

## 11.2 Enterprise workforce

As required:

- OIDC
- SAML
- later SCIM

## 11.3 Product clients

Use:

- OAuth device/authorization flow
- device key proof
- product audience
- entitlement decision
- device lease

## 11.4 Services/workloads

Use:

- short-lived workload identity
- no shared permanent secret
- least privilege

## 11.5 Kristi/tool runners

Use:

- ephemeral identity
- scoped capability
- approval token where required
- resource scope
- time scope
- policy decision

## 11.6 Policy-as-code direction

Start with Laravel policies for simple local rules.

Expose a policy-decision interface from day one.

OPA may be introduced when centralized cross-product/agent policy becomes justified.

---

# 12. LICENSING AND SECURITY MODEL

## 12.1 Customer-facing objective

Do not promise “uncrackable”.

The engineering objective is:

- difficult compromise
- small blast radius
- observable misuse
- revocable rights
- renewable leases
- verifiable releases
- recoverable data
- rapid response

## 12.2 Protocol

Use a compact signed token based on:

- CWT
- COSE

Do not invent custom crypto.

A lease should be able to carry:

- issuer
- product audience
- organization
- subject
- entitlement snapshot/version
- device public-key thumbprint
- release channel
- issued time
- not-before time
- expiry
- lease ID
- policy version
- signing-key ID

## 12.3 Default behavior

### Online
Short-lived renewable lease over TLS with device proof.

### Offline
Only when explicitly sold/approved.

Requires:

- bounded grace
- signed time policy
- periodic revalidation

## 12.4 Device assurance

Where supported:

- non-exportable TPM-protected key
- attestation

TPM cannot be the only route because hardware support varies.

## 12.5 Rust verifier

One Rust core owns:

- parsing
- signature verification
- time policy
- audience/product checks
- device binding checks
- entitlement decision inputs
- revocation decision
- deterministic test vectors

Language wrappers must be thin.

## 12.6 Key lifecycle

Private signing key must never live in the application database.

Use:

- KMS/HSM-backed signing
- separate code-signing and license-signing trust
- key IDs
- overlap during rotation
- signed public-key sets
- emergency revocation

---

# 13. RELEASE AND SOFTWARE SUPPLY CHAIN

Adopt:

- OWASP ASVS 5.0
- NIST SSDF
- SLSA provenance practices
- SBOM generation
- Sigstore/cosign where appropriate

Pipeline:

`Protected commit/PR`
→ `Static quality`
→ `Security scans`
→ `Reproducible build`
→ `SBOM/provenance`
→ `Protected signing`
→ `Staging`
→ `Browser/accessibility/DAST/performance/recovery tests`
→ `Approval`
→ `Progressive promotion`
→ `Audit`
→ `Advisory/revocation capability`

Continuous gates should include:

- format
- lint
- static typing
- unit tests
- architecture tests
- contract tests
- migration tests
- secret scanning
- dependency review
- SAST
- IaC policy
- license checks
- container checks when containers are used

Critical launches additionally require:

- independent penetration test
- threat-model review
- disaster-recovery exercise
- privacy/legal review
- load/soak tests

---

# 14. KRISTI GOVERNANCE MODEL

Kristi is an accountable operator.

Every action must follow:

`Intent → Plan → Approved Context → Policy → Execute → Verify → Audit → Notify`

## 14.1 Risk classes

### A — Reversible
Examples:

- draft
- classify
- analyze
- test
- staging cache purge

Kristi may execute under policy + audit.

### B — Guarded internal
Examples:

- dependency PR
- staging deploy
- bounded internal feature flag

Kristi may execute only with:

- automated tests
- rollback
- scope limits

### C — Public / financial
Examples:

- publish page
- marketing campaign
- price change
- production rollout

Kristi prepares the completed change/diff.

**Named human approval required.**

### D — Destructive / critical
Examples:

- root DNS
- signing keys
- mass deletion
- payout
- legal acceptance

Kristi may diagnose and stage only.

Requires:

- owner approval
- second control / break-glass procedure

---

# 15. CLOUD-ONLY VERIFIED-ZERO AI POLICY

## 15.1 Hard rules

- Generative inference is cloud-only.
- Local LLM inference is prohibited.
- Paid fallback is prohibited.
- Unknown cost is not free.
- Trial credits do not qualify as permanently free.
- Ambiguous “free” does not qualify.
- Price evidence must be current and explicit.
- Evidence expiry removes route eligibility.
- If no verified-zero route exists:

`NO_FREE_ROUTE_AVAILABLE`

## 15.2 Router registry should track

- provider/model ID
- capabilities
- context limit
- region
- current verified price
- price evidence source/date
- rate limits
- tool capability
- data-handling policy
- health
- evidence expiry
- observed latency/quality

## 15.3 Operational protections

- per-provider concurrency limits
- retry budgets
- circuit breakers
- prompt/data minimization
- redaction
- deterministic non-AI fallback where possible

## 15.4 AI safety tests

Test:

- prompt injection
- insecure output handling
- excessive agency
- secret leakage
- supply-chain poisoning
- context poisoning
- tool misuse
- unexpected spend paths

---

# 16. AUTONOMOUS DEVELOPMENT FACTORY

The Main Platform should be buildable with minimal owner intervention while preserving strict governance.

## 16.1 Control model

### GitHub
Source of truth for:

- code
- issues
- backlog
- contracts
- ADRs
- checkpoints
- CI evidence
- PRs

### Lightweight controller
Stateless/event-driven coordinator.

Do not make ephemeral local filesystem the authority.

### Workers
Use bounded disposable jobs.

Never rely on one endless AI process.

### AI
Cloud-only verified-zero routing.

### Reviewer
Independent verification path.

### Owner
Mobile-first approval for high-risk operations.

## 16.2 Ideal one-click flow

`START KMJ MAIN PLATFORM`

→ read canonical backlog  
→ select next independent task  
→ acquire writer lease  
→ verify current constraints  
→ select verified-zero AI route  
→ implement bounded slice  
→ run deterministic tests  
→ run independent review  
→ commit  
→ PR  
→ CI  
→ merge only after evidence  
→ staging/deploy only within policy  
→ checkpoint state  
→ report  
→ pick next task

## 16.3 Mandatory controller protections

Before public use, controller must have:

- authenticated start/control endpoint
- webhook signature verification
- idempotency key
- writer lease/lock
- task state machine
- durable checkpoint outside ephemeral instance
- audit trail
- provider registry
- verified price-evidence validation
- safe retry/circuit breaker
- no production authority by default

## 16.4 Cost discipline

Avoid continuous GitHub-hosted Actions polling.

Prefer:

- event-triggered CI
- bounded workflow dispatch
- low-frequency checks only where necessary
- Render/stateless control plane
- optional burst workers

Google Colab may be used only as a temporary/burst worker where policy and usage permit; it must not be treated as a guaranteed 24×7 coordinator.

---

# 17. RELIABILITY MODEL

## 17.1 Service tiers

### Tier 0 — Trust
- identity
- entitlement
- license renewal
- signing metadata

Must have strongest failure isolation and tested recovery.

### Tier 1 — Business
- portal
- catalog
- orders
- downloads
- webhooks

Highly available with queue/retry/reconciliation.

### Tier 2 — Experience
- public content
- docs
- search

Edge-cacheable where safe.

### Tier 3 — Enrichment
- AI suggestions
- semantic search
- analytics

May degrade or pause without blocking deterministic flows.

## 17.2 Operating principles

- edge cache public/catalog reads
- immutable content-addressed assets
- prioritized queues
- asynchronous AI where immediate response is unnecessary
- bulkheads for signing/licensing/media/exports/crawlers
- PostgreSQL connection pooling
- query budgets
- slow-query review
- backpressure
- OpenTelemetry from day one

## 17.3 Recovery contract

### PostgreSQL
- encrypted backups
- PITR
- separate account/region copy
- restore drills

### Releases
- immutable versioned storage
- signed manifests
- hash/signature validation

### Secrets/keys
- KMS/HSM-native recovery
- rotation plan
- no casual raw private-key export

### IaC/config
- version-controlled
- staging reproducible from a clean account

### Audit/security evidence
- append-only retained store
- restricted deletion
- evidence retrieval exercises

Do not declare RPO/RTO as guarantees until business-impact analysis and drills prove them.

---

# 18. PRIVACY, COMPLIANCE AND ACCESSIBILITY

Build into the data model:

- consent
- purpose
- retention
- export
- correction
- deletion
- processor propagation
- audit

Separate:

- marketing consent
- optional telemetry consent
- required product-operation data

Maintain a data inventory with:

- owner
- purpose
- lawful basis
- region
- retention
- processor
- deletion method

Security:

- encryption in transit
- encryption at rest
- tokenized provider-held payment data
- sensitive telemetry redaction

Accessibility target:

**WCAG 2.2 AA**

Use:

- automated checks
- keyboard testing
- screen-reader testing
- human review

India DPDP and other legal duties must be confirmed for actual launch by appropriate legal review; legal/tax behavior remains in replaceable adapters, not entitlement/licensing core.

---

# 19. PUBLIC EXPERIENCE, BRAND TRUTH AND CONTENT

KMJ should look premium through:

- strong typography
- restraint
- performance
- accessibility
- complete empty/error/loading states
- coherent design system
- truthful evidence

Never fabricate:

- customers
- offices
- awards
- certifications
- partnerships
- scale
- benchmarks

Product status vocabulary:

- Available
- Preview
- Research
- Planned

Public claims come only from approved facts.

---

# 20. SEO, MULTILINGUAL AND DISCOVERABILITY

## 20.1 Rendering

Indexable content should be server-rendered or pre-rendered.

## 20.2 Locale structure

Use explicit locale URLs such as:

- `/en/`
- `/hi/`

Use:

- hreflang
- x-default
- human-reviewed key translations
- glossary
- translation memory

Do not force redirect only because of IP/language.

## 20.3 Technical SEO

Require:

- canonical URL map
- robots control
- sitemap indexes
- 301 migration map
- correct HTTP status
- no orphan pages

## 20.4 Structured data

Only from visible approved facts.

Possible types:

- Organization
- Product
- SoftwareApplication
- Article
- Breadcrumb

## 20.5 Web Vitals target at p75

- LCP ≤ 2.5 s
- INP ≤ 200 ms
- CLS ≤ 0.1

Separate budgets for public pages and authenticated portal.

## 20.6 Content quality

Prefer:

- original expert work
- named author/reviewer
- evidence
- practical examples
- update date
- stable source URLs

Do not:

- mass-publish low-value AI pages
- create fake backlinks
- promise rankings
- create schema for facts not visibly supported

---

# 21. REPOSITORY FOUNDATION

Canonical layout:

```text
apps/
  platform/

packages/
  domain-*
  contracts/
  design-system/
  kristi-policy/

services/
  license-core/

infra/

docs/
  adr/

tests/
  architecture/

work/
  backlog.yaml
```

## 21.1 Engineering rules

- A module must not import another module’s persistence model.
- Providers sit behind adapters.
- Provider adapters need test doubles.
- Provider calls need idempotency where relevant.
- Material dependencies need an exit path.
- Destructive DB cleanup is not combined with the initial rolling migration release.
- Every feature includes authorization.
- Every feature includes audit.
- Every user-facing feature considers localization.
- Every user-facing feature considers accessibility.
- Every material operation considers observability.
- Every deployment-capable feature has rollback.
- AI-generated code receives the same review as human code.
- No AI may bypass tests, branch protection or approval.
- One authoritative writer at a time.
- Important PASS claims require independent evidence.

---

# 22. BUILD VS ADOPT

## 22.1 KMJ should build/own

- domain kernel and contracts
- catalog/entitlement policy
- licensing protocol
- Rust verifier
- Kristi orchestration/policy/audit
- verified-free AI router
- design system
- content QA
- provider adapters
- migration tooling

## 22.2 KMJ should adopt vetted standards/libraries

- Laravel
- React
- PostgreSQL
- OAuth/OIDC/WebAuthn
- CWT/COSE
- OpenAPI
- CloudEvents
- MCP
- A2A
- OpenTelemetry
- OPA when justified
- SBOM/Sigstore/SLSA tooling

## 22.3 Never invent

- cryptographic primitives
- TLS validation
- database drivers
- HTTP runtime
- password hashing primitives
- browser engines
- package managers
- payment-card storage

---

# 23. MASTER DELIVERY ROADMAP

This roadmap is **milestone-based, not date-promising**.

Trust-critical work does not advance because of a calendar date. It advances only after exit evidence.

---

## PHASE 0 — TRUTH AND BOUNDARIES

### Objective
Lock reality before expanding feature code.

### Deliverables
- glossary
- system context
- data classification
- threat model
- architecture decisions
- URL/content inventory
- public factual inventory
- metrics baseline

### Current status
**ACTIVE / PARTIALLY COMPLETE**

Done:
- P0-01 names and boundaries
- P0-03 foundational ADRs

Pending:
- P0-02 inventory of current public URLs, assets and approved facts

### Exit gate
- owner scope approval
- Main Platform / Cloud Nexus boundary encoded
- public-fact inventory exists
- migration inputs captured

---

## PHASE 1 — SECURE FOUNDATION

### Objective
Create reproducible, governed engineering foundation.

### Deliverables
- private repository
- CI
- CODEOWNERS
- protected branch/ruleset
- environments
- module skeleton
- architecture tests
- versioned API/event contracts
- Laravel runtime
- PostgreSQL target
- queue/outbox basis
- object-storage interface
- observability basis
- design-token basis
- baseline recovery/security tests

### Current status
**ACTIVE / MOST CORE SOFTWARE WORK COMPLETE**

Done:
- P1-02 architecture tests/module skeletons
- P1-03 OpenAPI/event contracts
- P1-04 Laravel 13 + React 19 runtime

Blocked:
- P1-01 final completion because `main` protection is not enabled

### Exit gate
- protected merge path
- reproducible clean build
- rollback path
- baseline security tests
- baseline recovery tests
- no architectural boundary regression

---

## PHASE 2 — ENTERPRISE CORE

### Objective
Build the central identity/tenant/catalog operating core.

### Deliverables
- identity baseline
- passkey baseline
- organizations
- membership
- roles/capabilities
- catalog
- portal shell
- operator console shell
- audit foundation
- privacy foundation
- tenant isolation
- policy interface

### Immediate implementation sequence

1. Organizations domain
2. Organization membership
3. Product/catalog domain
4. Entitlement authority
5. Tenant isolation tests
6. Passkey/account integration
7. Portal shell
8. Audit and privacy seams

### Exit gate
- tenant isolation PASS
- authorization PASS
- critical account/org journeys PASS
- no cross-module persistence leakage

---

## PHASE 3 — COMMERCE AND LICENSING

### Objective
Prove end-to-end commercial right → cryptographic product right.

### Deliverables
- provider-neutral payment adapters
- order/subscription ledger
- idempotent webhook handling
- entitlement policy
- license issuance
- Rust verifier
- activation/device ledger
- revocation
- offline policy
- release channels
- signed manifests

### First mandatory thin vertical slice

`Organization`
→ `Product`
→ `Entitlement`
→ `Signed Sandbox License`
→ `Product Validation`
→ `Revocation`

### Recommended split

#### Slice A — Authority core
- Organization
- Product
- Entitlement
- audit
- deterministic policy
- tenant isolation

#### Slice B — Cryptographic proof
- signed sandbox lease
- key separation
- Rust verifier
- deterministic vectors
- product-side validation
- revocation

#### Slice C — Commercial origin
- order/subscription ledger
- payment adapter
- reconciliation
- entitlement issuance from commercial policy

### Exit gate
- purchase-to-revocation flow PASS
- signing-key isolation PASS
- key rotation test PASS
- offline grace cases PASS
- device activation limits PASS
- revocation latency/mechanism PASS
- Rust wrapper conformance PASS

---

## PHASE 4 — KRISTI OPERATIONS

### Objective
Turn Kristi into a governed operating layer.

### Deliverables
- capability registry
- tool registry
- approved-context system
- risk classifier
- policy gate
- approval tokens
- executor
- independent verifier
- immutable evidence
- rollback references
- verified-zero AI router
- deterministic fallback paths
- mobile owner approval flow

### Exit gate
- risk-class tests PASS
- paid fallback impossible
- `NO_FREE_ROUTE_AVAILABLE` verified
- destructive actions blocked by policy
- rollback and verification proven
- audit evidence complete

---

## PHASE 5 — PUBLIC EXPERIENCE

### Objective
Build world-class public and content experience without sacrificing truth or performance.

### Deliverables
- corporate information architecture
- capabilities
- product pages
- documentation
- trust center
- insights/research
- support
- multilingual URLs
- structured data
- design system
- accessibility
- public performance
- SEO migration tooling

### Representative migration task
Migrate one real product page end-to-end before mass migration.

### Exit gate
- factual truth review
- WCAG 2.2 AA
- Web Vitals budget
- schema validation
- crawl/index validation
- no fabricated claims

---

## PHASE 6 — PRODUCT INTEGRATION

### Objective
Connect independent KMJ products and KMJ Cloud Nexus to released platform contracts.

### Deliverables
- product SDK
- Nexus adapter/SDK
- OAuth/product auth flow
- license validation SDK/wrappers
- webhooks
- release/update channels
- minimized telemetry
- outage/degraded-mode behavior

### Cloud Nexus rule
Cloud Nexus remains separate.

Integration happens through:

- versioned OpenAPI
- released event contracts
- SDKs
- authentication
- entitlement/licensing protocols

### Exit gate
- compatibility matrix PASS
- outage/degraded-mode PASS
- revocation PASS
- supported-version PASS
- no direct DB dependency

---

## PHASE 7 — MIGRATION AND CUTOVER

### Objective
Move from old public site to the new platform without uncontrolled risk.

### Deliverables
- repeatable migration
- data reconciliation
- URL redirect map
- metadata migration
- schema review
- dark deployment
- synthetic checks
- shadow checks
- internal cohort
- controlled public cohort
- rollback window
- completed owner production-change form

### Exit gates

#### Content parity
Every valuable current page maps to:
- new page
- or intentional 301

#### Data parity
- reconciled counts
- sampled records
- repeatable/idempotent migration

#### Security
- critical/high blockers closed
- key rotations tested
- independent findings triaged

#### Reliability
- backup restore tested
- degraded mode tested
- queue replay tested
- rollback exercised

#### Performance
- representative global/device budgets met

#### Product compatibility
- Nexus and sandbox clients pass supported-version/outage cases

#### Owner approval
Completed production-change form shows:

- release/version
- migrations
- redirects
- DNS/CDN changes
- monitoring/observers
- rollback path

### Final rule

No public Save, Publish, DNS or production mutation is authorized merely because development is complete.

Explicit owner approval is still required.

---

# 24. IMMEDIATE MASTER BACKLOG — ORDER OF EXECUTION

The next work should follow this order unless a verified blocker requires a change.

## Priority 0 — Governance blocker
Enable `main` branch protection/ruleset.

## Priority 1 — Finish Authority Slice A
Complete and independently test:

- Organizations
- Memberships
- Catalog Product
- Product lifecycle/status
- Entitlement grant
- Entitlement revocation
- tenant isolation
- idempotency
- audit events

## Priority 2 — Build Slice B
Implement:

- licensing domain
- signed sandbox lease
- signing boundary
- public-key distribution
- Rust verifier
- deterministic vectors
- product validation
- revocation path

## Priority 3 — Passkey + organization integration
Connect current Laravel authentication with:

- organization creation
- owner membership
- role/capability model
- tenant context
- step-up path

## Priority 4 — Transactional outbox
Introduce durable domain events and idempotent consumers.

## Priority 5 — Audit foundation
Append-only security/approval/business transition evidence.

## Priority 6 — Release trust
Implement:

- release manifest
- artifact digest
- provenance reference
- sandbox artifact
- signing boundary

## Priority 7 — Commerce origin
Provider-neutral:

- orders
- subscriptions
- adapter interface
- webhook validation
- reconciliation
- entitlement issuance

## Priority 8 — Kristi safe foundation
Capability registry + policy + approval + verification, staging-only initially.

## Priority 9 — Public IA
Build the public information architecture and one representative product page.

## Priority 10 — Inventory old site
Complete P0-02 before broad migration.

---

# 25. ACCEPTANCE STANDARD FOR EVERY FEATURE

A feature is not “DONE” merely because code exists.

For relevant features, DONE requires evidence for:

- functional behavior
- authorization
- tenant isolation
- validation
- idempotency
- audit
- localization
- accessibility
- observability
- rollback/degraded behavior
- architecture boundaries
- contract compatibility
- security review
- deterministic tests
- CI PASS

Production-capable features also require:

- staging evidence
- rollback evidence
- owner approval when risk class requires it

---

# 26. STATUS LANGUAGE

Use only these meanings:

### `PLANNED`
Approved direction, not implemented.

### `ACTIVE`
Implementation currently in progress.

### `IN_REVIEW`
Code exists and is under PR/verification.

### `VERIFIED`
Independent tests/evidence passed.

### `DONE`
Merged/accepted and all required gates for that scope passed.

### `BLOCKED`
Cannot advance without a specific dependency or owner action.

### `DEFERRED`
Deliberately postponed; not a failure.

Never write “PASS” or “DONE” without actual evidence.

---

# 27. SECURITY RED LINES

The following are forbidden design shortcuts:

- client-only license authority
- plaintext authoritative license state
- editable local JSON as final authorization
- shared permanent service secrets
- raw signing private key in application DB
- unverified payment webhook as authority
- cross-module database writes
- AI-generated public facts
- silent paid AI fallback
- local LLM inference
- destructive migration in same release as initial additive migration
- production DNS/publish without approval
- “unbreakable” marketing claims
- fake customer/certification/scale claims
- direct product access to Main Platform database

---

# 28. WORLD-CLASS DEFINITION

The project is world-class only when evidence supports all of the following.

## Clarity
A new engineer can find the source of truth, contract, owner and runbook for each critical capability.

## Security
ASVS-based verification, threat model, least privilege, signed supply chain, revocation and independent testing.

## Reliability
Internal SLOs, tested recovery, bounded failure domains and visible customer impact.

## Product control
One entitlement decision is applied consistently across KMJ products with defined degraded modes.

## Automation
Kristi completes approved low-risk tasks with evidence and stops high-risk work at approval.

## Experience
Fast, accessible, coherent, multilingual and responsive.

## Discoverability
Crawlable URLs, truthful structured data, original expertise and no spam/guarantees.

## Maintainability
Routine upgrades, enforced boundaries, replaceable dependencies and documented operations.

---

# 29. FUTURE EXPANSION — CANDIDATE, NOT DAY-ONE CORE

These technologies/ideas can be considered only after measurable need:

- Temporal
- NATS JetStream
- Kubernetes
- pgvector
- confidential compute
- eBPF observability/security
- Firecracker isolation
- WASM extension/runtime use
- PQC hybrid cryptography
- formal verification
- P2P resilience/distribution

P2P, if ever added, must remain a **resilience/distribution layer**, not the source of truth for money, entitlement, identity or legal authority.

---

# 30. CHANGE MANAGEMENT

Any future architectural change must answer:

1. What problem is proven?
2. What current constraint is failing?
3. What simpler alternative was considered?
4. Does it change a system boundary?
5. Does it change authority ownership?
6. Does it create paid/runtime/vendor lock-in?
7. Does it affect Cloud Nexus separation?
8. Does it alter production approval risk?
9. What migration and rollback exist?
10. What independent test proves the change?

Material architecture changes require an ADR.

---

# 31. NEW-CHAT / NEW-AGENT CONTINUATION BLOCK

When this project is moved to another chat, agent or engineering environment, provide this block together with this file:

```text
CONTINUE KMJ TECHNO MAIN PLATFORM.

Treat this as continuation, not a new project.

CANONICAL REPO:
kmjtechno/kmj-main-platform

MAIN BRANCH:
main

MASTER BLUEPRINT:
KMJ_TECHNO_MAIN_PLATFORM_MASTER_ROADMAP_BLUEPRINT_V1_0.md

SYSTEM BOUNDARIES:
- Main Platform = central business/product/customer/licensing/release/automation authority.
- KMJ Cloud Nexus = separate engineering IDE; do not modify or merge into Main Platform.
- Kristi = governed operator through policy, tools, verification and audit.
- Products consume released contracts; no direct DB access.

HARD RULES:
- cloud-only generative AI
- NO local LLM inference
- only current explicit verified-zero AI routes
- unknown cost != free
- paid fallback prohibited
- no route => NO_FREE_ROUTE_AVAILABLE
- one authoritative writer
- independent verification before PASS
- no production publish/DNS/billing/destructive/signing-key action without owner approval
- client is never final license authority
- private signing key never in application DB

CURRENT MASTER THIN SLICE:
Organization -> Product -> Entitlement -> Signed Sandbox License -> Product Validation -> Revocation

CURRENT ACTIVE DEVELOPMENT DIRECTION:
Finish authority slice, then licensing/Rust verifier/revocation, then broaden enterprise core.

DO NOT CLAIM DONE WITHOUT CI / TEST / REVIEW EVIDENCE.
```

---

# 32. DOCUMENT MAINTENANCE RULE

This file should remain stable.

Do not rewrite the entire blueprint after every small commit.

Update only:

- version
- implementation snapshot
- roadmap statuses
- newly accepted ADR decisions
- newly proven blockers
- owner-approved scope changes

Recommended versioning:

- V1.0 — initial canonical master
- V1.1 — status/evidence refresh
- V1.x — compatible roadmap refinements
- V2.0 — material architecture or product-boundary change

---

# 33. MASTER CONCLUSION

KMJ TECHNO Main Platform should be built as a **secure, modular, evidence-driven enterprise operating platform**, not as a conventional website and not as an uncontrolled collection of AI agents.

The correct sequence is:

**Truth**
→ **Secure Foundation**
→ **Enterprise Authority**
→ **Licensing Proof**
→ **Governed Automation**
→ **Public Experience**
→ **Product Integration**
→ **Controlled Cutover**

The most important near-term proof remains:

`Organization → Product → Entitlement → Signed Sandbox License → Product Validation → Revocation`

Do not expand breadth faster than authority, security, revocation and recovery can be proven.

---

# APPENDIX A — CANONICAL SOURCE BASIS

This V1.0 master blueprint consolidates:

1. `KMJ_TECHNO_Platform_Blueprint.docx`
   - Fresh Foundation, Architecture and Delivery Roadmap
   - research cut-off 9 September 2026

2. Live repository:
   - `kmjtechno/kmj-main-platform`

3. Accepted merged implementation:
   - architecture foundation
   - P1-02 architecture tests
   - P1-03 API/event contracts
   - P1-04 Laravel 13 + React 19 runtime

4. Live implementation snapshot:
   - `main` commit `aff6596ab239fc72be14aa5d717ec00708401303`
   - active branch `slice/authority-core-v1`
   - branch protection blocker still open at snapshot time

5. Older project handoffs are candidate context only where they do not conflict with this blueprint.

---

# APPENDIX B — LOCKED PROJECT IDENTITY

**Company:** KMJ TECHNO  
**Main Platform:** KMJ TECHNO Main Platform  
**Domain:** `kmjtechno.com`  
**Repository:** `kmjtechno/kmj-main-platform`  
**Cloud engineering system:** KMJ Cloud Nexus — separate system  
**Governed assistant/operator:** Kristi  
**Primary architecture:** Modular monolith + event-driven seams  
**Primary business runtime:** Laravel 13 / PHP 8.5  
**Authenticated UX:** Inertia 3 / React 19 / TypeScript  
**Authority database:** PostgreSQL 18 target  
**Native licensing verifier:** Rust  
**AI policy:** Cloud-only, verified-zero, no paid fallback  
**Production policy:** Explicit owner approval for high-risk/public/financial/destructive actions  

---

**END OF MASTER ROADMAP & BLUEPRINT — V1.0**
