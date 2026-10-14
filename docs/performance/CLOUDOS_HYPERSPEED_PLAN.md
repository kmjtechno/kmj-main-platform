# KMJ Main Platform — CloudOS HyperSpeed v1 (owner goal, 2026-10-13)

**Goal:** Keep kmjtechno.com extremely responsive under massive international traffic with CloudOS managing hosting. Ten million simultaneous users is an **unverified capacity ambition**, not an engineering claim or a target met by a single free VPS.

**Versioned shared policy:** `contracts/performance/main-platform-hyperspeed-v1.json` in both repositories.

## Critical separation of traffic

1. **Edge:** Content-hashed Vite JS/CSS/fonts and approved anonymous assets are immutable. CDN cache configuration and hit ratio must be independently checked; CloudOS FrankenPHP candidate caches only `/build/assets/*` for a year. Do not cache cookie-/session-bearing Inertia HTML, personal profiles, API tokens, signed licensing, checkout, email verification or Super Admin pages on any shared edge.
2. **Dynamic web:** Stateless replicated FrankenPHP classic-mode Laravel behind CloudOS-managed Caddy ingress (no Nginx); `/up` health checks, connection/drain limits and failure isolation. Worker mode/Octane only after state-leak and memory regressions are measured.
3. **Authority DB:** PostgreSQL remains single authority with indexed bounded queries, deliberately capped connection pools, read replicas for genuinely read-only workloads when measured and provider-backed. Public catalog DB work is a current scale candidate; introduce cached projections with versioned invalidation and tenant/public separation after correctness tests. Never cache license/entitlement or payment decisions across users.
4. **Shared state:** CloudOS runtime example sets `CACHE_STORE=redis`, `SESSION_DRIVER=redis`, `QUEUE_CONNECTION=redis` backed by isolated Redis/Valkey. Real HA/session migration, correct cookies and TLS are required before enabling. No secret values are committed.
5. **Work queues:** Mail, search indexing, analytics, image processing and permissible side effects leave the request critical path. Payment/webhook entitlement transitions remain idempotent, authenticated and observable; job retries must never duplicate a charge or license.
6. **Autoscaling:** Use only **measured sustainable RPS per replica**, CPU, RAM, p95/p99 latency, queue age, connection pressure and error budget to recommend replicas. Maintain at least two replicas on separate fault domains and reserve headroom. A finite owner-approved cloud-node budget and cross-node encrypted transport are mandatory. CloudOS candidate planner `src/services/hosting/capacity_plan.py` is a dry-run, not an active autoscaler.
7. **Overload:** Admission control and retries are scoped. Never retry non-idempotent payment writes without idempotency keys; noncritical traffic may receive bounded 429/503 + Retry-After instead of exhausting DB/queue and taking everyone down. Never falsely display success when email, license or order delivery did not complete.

## Benchmark/release sequence

- Establish a **real** baseline for `/up`, anonymous homepage/products, customer login, purchase/webhooks, license validation and Super Admin with staging-only data.
- Use `python3 scripts/perf/cloudos_bounded_local_probe.py --execute-local-staging --requests 50 --workers 4 --path /up` **only after** verifying 127.0.0.1:8080 is the isolated staging runtime; local probe is capped at 1000 requests and 16 workers. It is NOT evidence for high-scale distributed traffic.
- CloudOS candidate `src/services/reverse_proxy/scaling_caddy.py` supports **same-node loopback** multi-port backends with Caddy /up health probes and least-connection routing. A separate CloudOS authenticated multi-node route backend with mTLS and node anti-affinity is required before claiming globally distributed capacity.
- Upgrade through measured multi-replica tests, worker/DB pressure, multi-node failover, restore, then distributed traffic ramps. Record RPS, concurrent *in-flight* work (not merely logged-in browsers), edge hit ratio, TTFB p50/p95/p99, error rate, DB pool and cache pressure, queue backlog/oldest age, node availability and budget.
- **Initial objective, not a proven result:** cached public edge p95 TTFB <=200ms, dynamic public <=500ms, authenticated <=800ms, <=0.1% request errors and 99.95% monthly availability. Refine only from comparable geography/device/traffic-weighted measurements.
- Only after repeatable stress tests and proven infrastructure capacity may anyone publish claims about millions/crores of users.

## Immediate production safeguards

Existing website, customer sessions, DNS, databases, payment state, mail configuration and live Nginx service remain unchanged until approved migration/reverse migration completes. No unapproved external paid CDN or on-demand cloud servers. HyperSpeed engineering is a **CloudOS-owned integrated product responsibility**, not a magic property of Laravel or FrankenPHP.

**2026-10-13 state:** contract and offline candidate configs/planner/probe committed to review branches; NOT deployed, NOT stress tested, NOT proven to serve millions.
