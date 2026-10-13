# ADR-009 — KMJ Main Platform hosted on KMJ CloudOS

**Decision:** Accepted / owner locked 2026-10-13. **Implementation:** NOT DEPLOYED.
**Supersedes:** earlier ambiguity that CloudOS might only be a future optional hosting substrate. Does **not** reverse the 2026-09-16 supersession of the legacy staging-homepage mirror.
**Cross-repository contract:** `contracts/deployment/main-platform-cloudos-v1.json` (byte-for-byte counterpart in CloudOS). CloudOS companion: `docs/architecture/MAIN_PLATFORM_HOSTING_V1.md`.

## 1. Fixed responsibility split

- **Main Platform:** public `kmjtechno.com`, identity/auth, organization and customer records, operator/Super Admin, commerce and approved payment reconciliation, entitlements, signed licensing and revocation, product catalog, release governance, customer support and audit. It owns application databases and domain policies.
- **CloudOS:** independent Linux hosting/data plane, node/fleet lifecycle, app runtime isolation, ingress, certificates integration, storage volumes, backups, process/service health, monitoring, safe deployment slots and rollback. It owns infrastructure lifecycle, **not** Main Platform identity, licensing or payment authority.
- **CodeBridge/Cloud Nexus/Kristi:** separate clients/engineering tools, never hosting control or a direct cross-product database bridge.

Main Platform runs **as an isolated CloudOS-managed workload**. The two projects remain separate repositories and release pipelines, connected by versioned authenticated APIs, signed contracts and narrowly scoped events. CloudOS is not merged into Laravel and Laravel is not merged into CloudOS.

## 2. Break the circular hosting/license dependency

CloudOS must not need a live Main Platform to **boot, restart, route or continue an already authorized workload**. Main Platform being hosted in CloudOS must not self-authorize CloudOS or mint its own license to start.

Provide a narrowly scoped, audited platform-internal bootstrap policy provisioned independently of the live application. Customer workloads still require their own valid signed entitlements. CloudOS caches last-known-good signed authorization and uses explicitly bounded offline grace on temporary central/license outages; revocations are enforced on reconnection subject to the declared grace policy. Do not introduce an unbounded entitlement bypass.

The existing Phase-1 central-outage hosting-survival and Phase-2 data-plane/control-plane-restart survival contracts are release blockers, not optional optimizations.

## 3. Target deployment composition

1. CloudOS-managed isolated Linux application tenant/workload for immutable Main Platform revision: PHP-FPM/Laravel web service behind protected ingress, built frontend assets and dedicated least-privilege processes for queue workers and scheduler.
2. Dedicated PostgreSQL database/roles (Main Platform is the authority), Redis/Valkey-compatible cache/queue, durable encrypted volumes; CloudOS may provision and back up but not directly mutate commercial data.
3. Secrets injected only at runtime from an appropriately secured vault/host secret source. No public keys confused with license private signing keys; no production secrets in Git, CloudOS JSON state or telemetry.
4. First-party transactional mail isolated as a service; do not gate live email recovery on completion of the full Gmail-class mailbox product. Real sending, SPF/DKIM/DMARC, outbound port/PTR, queues/bounces and controlled inbox+signed-link proof are required.
5. Explicit application egress/ingress policies, authenticated CloudOS deployment endpoint, scoped rollout identity, TLS, health-check and audit evidence.
6. Provider-neutral manifests and backups. Static IP, old/new VPS addresses and physical hostnames belong to **environment manifests**, not a source-code assumption. Do not hardcode former staging origin IPs.

CloudOS may host the application without running it as a child of the CloudOS *control plane*. Its runtime and data plane must remain independently restartable.

## 4. Implementation order (engineering direction)

**P0-A — Contract freeze:** version both sides of this JSON deployment contract and validate matching IDs/semantics. Maintain exact API compatibility and no direct database access; document tenant bootstrap and process isolation.

**P0-B — CloudOS hosting readiness:** demonstrate applicable HOST, DB, backup/restore, TLS/DNS, security/isolation, provider activation, renewal/outage and rollback gates with **real** evidence (not unit tests or synthetic status JSON). Keep Linux-first acceleration only within the CloudOS approved gate policy.

**P0-C — Main Platform image/release:** build a pinned immutable artifact, make configuration CloudOS-targetable, implement readiness/liveness checks and bounded migrations, queue/scheduler supervision, maintenance mode, backup and roll-back preflight. No privileged root shell from customer UI.

**P0-D — Mail and commercial flows:** resolve registration verification mail, password reset, webhook receipt/replay/idempotent order-to-entitlement, native signed license and revocation. Customer-facing failures must be truthful.

**P0-E — Staging on CloudOS:** native Main Platform, not a mirrored legacy homepage. Test root, registration, email verification, operator/Super Admin, products, license, payment webhooks, queues, backups, node restart, authorization-center outage and recovery. Require signed exact-SHA release gates and current CloudOS execution evidence.

**P0-F — Canary and production migration:** backup and independently verify restore; preflight data copy and consistency, TLS ingress and DNS; keep current production site operational. Progressive cutover only after all required gates and explicit owner approval, with reverse cutover + DB/queue rollback plan. Never treat a green HTTP 200 as full success.

## 5. Non-goals / safety

- No old staging homepage mirroring and no early DNS mutation.
- No direct CloudOS SQL writes into Main Platform, and no CloudOS SaaS licensing authorization derived from just a successful payment.
- No indefinite platform outage exemption for customer workloads.
- No assumption CloudOS is production-ready because a roadmap YAML, unit test or `MAIL-001_PASS.json` exists.
- No paid hosting, CI, third-party transactional mail or AI fallback added without scope/cost verification.

## 6. Minimum CloudOS-hosted cutover acceptance

- Exact immutable app and CloudOS release IDs; independent CI and documented rollbacks.
- Restored PostgreSQL backup on isolated environment; transaction/queue consistency and key custody checked.
- Ingress TLS, domain isolation, migration/downgrade safety, deployment audit and health probes verified.
- Login/passkey, registration verification inbox link, password reset, operator controls, Cashfree/Razorpay webhook authentication/replay tests, entitlements and revocation verified in staging with sandbox inputs.
- A real CloudOS-control-plane outage does **not** take down an already-running Main Platform; CloudOS can recover/restore while license authority is temporarily unavailable within policy.
- Existing public release preserved until explicit production cutover authority. After promotion, actual external probing and rollback rehearsal evidence captured.

**Evidence status as of 2026-10-13:** TARGET LOCKED, IMPLEMENTATION/INBOX/RECOVERY/PRODUCTION CUTOVER **UNVERIFIED**. Do not claim released.
