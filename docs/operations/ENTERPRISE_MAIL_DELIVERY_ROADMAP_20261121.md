# KMJ TECHNO — Enterprise Mail Delivery Architecture & Roadmap

**Status:** Owner policy / evidence-based design, **not** a production-readiness certificate.
**Date:** 21 November 2026. **P0 tracking:** [#391](https://github.com/kmjtechno/kmj-main-platform/issues/391).
**Authority:** [Master Roadmap](../../KMJ_TECHNO_MAIN_PLATFORM_MASTER_ROADMAP_BLUEPRINT_V1_0.md), [CLAUDE.md](../../CLAUDE.md), [Release Gate](../../RELEASE_GATE.md), [ADR-002](../adr/ADR-002-modular-monolith.md).
Newer owner decisions override generic older runbook suggestions where they conflict.

## Locked deployment policy

1. **Incoming business inbox:** `info@kmjtechno.com` is received through **Cloudflare Email Routing**, forwarded to the owner-controlled existing Gmail destination. Preserve Cloudflare-managed MX, routing rule and other DNS records. Cloudflare routing is *not* the application's outbound SMTP service.
2. **Outbound transactional messages:** Live Laravel uses the **`sendmail`** transport into existing **Postfix on KMJ-elite**. Postfix delivers **directly to destination MX as primary** (`relayhost` empty, `default_transport=smtp`).
3. **Fallback only:** Existing `smtp_fallback_relay=[smtp-relay.brevo.com]:587`. Never configure Brevo as the global primary `relayhost`, flip Laravel into Brevo SMTP, or add another self-hosted mail product merely to clear a queue. Postfix fallback is for eligible connection/delivery failures; it does **not** guarantee retry on every recipient-side rejection.
4. **DKIM:** Existing OpenDKIM on localhost `127.0.0.1:8891`; preserve existing selector, identity and private keys. Do not expose port 25/8891 publicly to make a probe pass.
5. **Single VPS and cost:** Main Platform runtime, signing/deployment operations and mail production are on **KMJ-elite only**. No Google-VPS dependency, new recurring subscription, or unknown-cost failover.
6. **Change controls:** No DNS change, production release pointer/DB mutation, credential export/rotation, Postfix queue purge/flush, new delivery blast, or bypass of protected release and owner approval gates as part of a read-only investigation.

## 21-Nov-2026 evidence snapshot — do not carry PASS forward

| Evidence | What it proves | What it does NOT prove |
| --- | --- | --- |
| Live `kmj:mail:doctor --json`: `environment=production`, `transport=sendmail`, `can_attempt_external_delivery=true`, `live_delivery_proven=false` | Application can attempt delivery with current transport | Recipient delivery, valid signed links |
| `systemctl` and `ss`: Postfix active; OpenDKIM was found inactive and then started; localhost milter listening | Service and socket available at inspection | Continuous availability, correct signature on every mail |
| `postconf`: `relayhost=`; `smtp_fallback_relay=[smtp-relay.brevo.com]:587`, `default_transport=smtp`, `smtp_sasl_auth_enable=yes` | Direct-to-MX primary with configured Brevo fallback | Which specific route each historic message took |
| Earlier queue: 14 deferred, then 12; 12 recipient statuses had `525` | Historic Brevo IP authorization failure | Password failure or permanent recipient rejection |
| Connected Brevo security alert confirmed `150.242.200.81` added to authorized IP list at 11:51Z | Owner account authorized Elite's outbound source IP | New SMTP handshake/recipient receipt |
| Latest operator `postqueue -j`: `QUEUE_MESSAGES=0`, `DEFERRED=0`, `LAST_RECORDED_525=0` (12:50Z) | Local Postfix queue empty at that instant | **All messages delivered:** some may have expired/bounced or otherwise left queue |
| `postconf -h maximal_queue_lifetime` = `5d` | Normal queue expiry threshold 120 h | Fate of any individual message; a previous oldest was about 137 h |
| Connected Cloudflare zone: Email Routing `ready`, `info@` rule enabled, Cloudflare MX; SPF includes Elite IPv4 and Cloudflare | Inbound routing configured; direct outbound IPv4 authorized by SPF | Outbound DKIM alignment / DMARC / recipient-specific inbox success |
| Historical owner Gmail: 11-Nov Main Platform Laravel → sendmail → owner Gmail received | Path has worked before | Fresh end-to-end registration/reset verification |

The evidence is dated and bounded. Treat a `0` queue as **drained**, not **delivered**. If a message disappeared, check redacted Postfix `status=sent` versus `status=bounced` / `expired` counts and delivery-status notifications; do not read or reproduce other recipients' messages.

## P0 — release-blocking customer auth mail acceptance

- [x] Observe production mailer `sendmail` rather than trusting repository defaults.
- [x] Verify direct-primary / Brevo-fallback settings and authorized outbound Brevo IP.
- [x] Restore OpenDKIM socket/service; validate live readiness probe.
- [x] Confirm Cloudflare inbound `info@` forwarding and DNS remain intact.
- [x] Obtain latest queue count and distinguish queue-clear from delivered.
- [ ] Reconcile the old queue: redacted Postfix transport event counts for sent, bounced, expired, deferred, without queue IDs, addresses, subject or body in chat.
- [ ] Perform **one** owner-approved, dedicated Laravel **verification** test to a pre-approved owner-controlled inbox. Verify actual message arrival, HTTPS correct-domain link, time-bound signature, correct-account verification, resend limits and no duplicate unverified account.
- [ ] Perform **one** separate owner-approved Laravel **password reset** test. Verify inbox receipt, token expiry, single-use behavior and no account enumeration. Do not show or paste signed links or reset tokens.
- [ ] Inspect actual received mail headers for **SPF / DKIM / DMARC alignment**, and for direct-vs-Brevo path classification. Readiness JSON alone is insufficient.
- [ ] Validate live release SHA, worker/scheduler states, staging gates and post-cutover smoke on the **actual** candidate. Closed/unmerged PR #948 is **not** needed for existing working `sendmail`.
- [ ] Only then update #391 to P0 PASS with redacted evidence and timestamps.

## P1 — durable, observable, safe operations (planned, not implemented claims)

1. **Mail health evidence:** Protected, root-owned, fixed read-only Supervisor profile for queue counts, age buckets, recent `sent/bounced/deferred/expired` aggregated counters, SMTP error-class histogram, DKIM service/socket and current transport fingerprints. No shell, caller-selected path, secret or raw logs.
2. **Alerting:** Notify owner on `opendkim` inactive, sustained deferred backlog, repeated `525/535`, age nearing `5d`, auth-mail failure or unexpected mail-routing drift. Bound alert cadence and redact all personal data.
3. **Delivery ledger:** Track application notification intent → dispatch attempt → Postfix accepted → downstream accepted/bounced/suppressed, using opaque correlation IDs. Never treat a queue enqueue, SMTP submission success or `0` queue as final inbox proof. Persist only minimal metadata with retention/privacy controls.
4. **Idempotent jobs:** Follow ADR-002, use existing transactional outbox patterns only where source code proves they apply, with bounded retries, backoff, deduplication, dead-letter/reconciliation and separate auth-mail priority. Do not assume the current event outbox already wraps auth mail.
5. **Provider adapter boundary:** Preserve `email: adapters_only` in `architecture/modules.yaml`. Direct Postfix primary remains operator-owned; Brevo is fallback through the existing Postfix configuration. A future provider rotation must be guarded and evidence-backed.
6. **Safe recovery:** Rehearse a disposable staging restore and historical delayed delivery classifications. Document rollback for configuration changes; never silently extend queue lifetime to hide errors.

## P2 — world-class product experience and trust gates (planned)

- KMJ-branded **HTML + plain text** transactional templates in the locked theme, accessible mobile/desktop/low-bandwidth layouts; no spoofed urgency or insecure third-party tracking.
- Verified-domain, signed, expiring account email links; single-use password reset, resend anti-abuse limits, per-account/tenant rate limits and safe user-visible failure states.
- Owner-only mail operations dashboard: honest states **Ready to attempt / Provider accepted / Delivered evidence / Deferred / Bounced / Unknown**, with role-based controls, audit of every action and no raw address exposure by default.
- Proposed, **not achieved** internal SLOs for *application submission and bounce-detection latency*; do not advertise an inbox-delivery guarantee as the receiver controls filtering.
- Regression gates: unit tests, isolated Postfix simulator, outbound SPF/DKIM/DMARC tests against an owner-controlled inbox, production cutover/rollback and accessibility QA. Evidence belongs to the exact SHA and run.

## Safe operator triage (read-only)

```bash
systemctl is-active postfix opendkim
postconf -h relayhost smtp_fallback_relay default_transport maximal_queue_lifetime
cd /home/kmjprod/current/apps/platform
runuser -u kmjprod -- php8.4 artisan kmj:mail:doctor --json
sudo postqueue -j | python3 -c 'import sys,json,collections; m=[json.loads(x) for x in sys.stdin if x.strip()]; print("MESSAGES",len(m)); print("STATES",dict(collections.Counter(x.get("queue_name","unknown") for x in m)))'
```

The mail doctor is a configuration probe, not a delivery monitor. Do not expose `.env`, raw `postqueue -p`, actual envelope recipients, SMTP credentials, complete logs, signed verification/reset URLs or token values.

## Do-not-do and exit conditions

- Do **not** overwrite Cloudflare Email Routing / its MX to satisfy outbound tests.
- Do **not** treat generic older `MAIL_MAILER=smtp` recovery steps as mandatory when live `sendmail` is configured and working; switching is a **separate approved design change**.
- Do **not** automatically send messages, requeue or flush queues after a Brevo IP authorization, particularly when old messages may be aged out.
- **WORLD-CLASS DONE:** Full P0 delivery proof + repeatable root-safe observability + security/privacy testing + staged recovery and production release evidence; until then report honest PASS/FAIL per component.
