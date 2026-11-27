# KMJ Mail — Self-Owned AI Communications Platform Roadmap (Draft V0.1)

**Owner direction:** 11 September 2026, reaffirmed 13 October 2026.  
**Status:** Proposed engineering roadmap; **NOT an implemented/released product**.  
**Scope:** A premium first-party email/communications product, not merely a transactional-email script, with a goal to outperform Gmail on selected, measurable business UX/AI/privacy workflows. Gmail/global provider deliverability parity must be proven, never presumed.  
**Canonical platform alignment:** `KMJ_TECHNO_MAIN_PLATFORM_MASTER_ROADMAP_BLUEPRINT_V1_0.md`, `architecture/modules.yaml` (`provider_boundaries.email: adapters_only`), `docs/adr/ADR-007-hosting-provider-compliance-guard.md`.  
**Issue:** #393. **Active production incident:** #391; **unmerged app safety patch:** #390.

## 1. Non-negotiable product requirements

- **Own KMJ-controlled mail service and user experience**, without mandatory Brevo/Gmail/SendGrid/Mailgun paid SMTP/API relays, external SaaS webmail, or proprietary single-provider lock-in.
- Third-party **mail protocols/standards are unavoidable** for Internet interoperability: DNS, recipient-side mail servers and reputation rules. Use secure, vetted open-source components instead of reimplementing cryptographic primitives or inventing SMTP/IMAP/TLS. A host/VPS provider is still necessary.
- **Company operations:** `@kmjtechno.com` staff mailboxes, aliases, group addresses, shared inboxes, department support queues, delegated access and role-based control. Owner-operated domain onboarding and tenant isolation.
- **User experience:** fast web and future mobile inbox; mail threads, labels/folders, rules, contact list, calendar integration, powerful traditional and semantic search, conversation grouping, attachments, rich and plain text, templates/signatures, scheduled send, undo send when technically possible, keyboard shortcuts, accessibility, localization, export/import and offline draft access.
- **Intelligence:** consent-based AI priority inbox, compact thread summaries, multilingual drafting/replies, translation, semantic search, action extraction, suggested follow-ups and phishing/spoof awareness. Default least-data context, encrypted/private index, auditable outputs and review before external sends; core mail remains fully operational **without AI**. Use KMJ ModelFabric's governed free/local-first routing and defined fail-closed policy, not an unbounded paid API.
- **Enterprise/admin:** full mailbox/alias/team provisioning, custom roles, audit, quotas, retention, legal/privacy requests, backup/restore, account recovery, security alerts, SSO/passkeys/MFA where appropriate, abuse control. Main Platform remains authoritative for identity and entitlements; mail stores remain a separate data plane.

## 2. Product/system boundaries

| Component | Owns | Must not own |
|---|---|---|
| KMJ Mail | Mail transport runtime, message queues, inbound/outbound policy, mailbox index/storage, web/mobile client, search, spam decisions, mail audits | Product licensing source of truth, global business billing |
| KMJ CloudOS | Approved VM/network/storage placement, health, backup, load monitoring, infrastructure automation, TLS/network evidence | User mailbox/entitlement authority |
| KMJ Main Platform | Identities, organizations, RBAC grants, subscriptions, product entitlement and secure transactional-notification adapter | Actual mailbox database, IMAP server, mail secret vault |
| ModelFabric / Kristi | Optional privacy-governed AI workflows, tool approvals/audit | SMTP signing authority, autonomous mass sends, ability to bypass anti-abuse |

Main Platform communicates via an authenticated, versioned transactional-mail contract with deterministic idempotency, queue status and delivery-event receipts. Customer identities/mailboxes cannot be exposed through shared database access.

## 3. Phased engineering roadmap

### MAIL-00 — Reality / feasibility: required before any public outbound SMTP

1. Read **hosting provider acceptable-use/email/spam policy**, service limits and outbound-port policy. Use no mail traffic until compliant.
2. Validate allocated sender IP reputation, stable IP ownership, **outbound TCP 25**, incoming TCP 25 (if mailboxes needed), TLS-enabled SMTP submission 587, IPv4/IPv6 consistency, reverse DNS/PTR **matching** mail hostname and forward A/AAAA, DKIM key operation and outbound queuing reliability. Changing PTR may need hosting-provider control.
3. Define per-domain and per-tenant mail flow, security/threat model, retention, postmaster/abuse contacts, DNS change plan, rollback and spam-compromise playbook.
4. Record each CHECK as **PASS/FAIL/BLOCKED**. If port 25 or rDNS/PTR is not available, **do not invent SMTP deliverability or launch a mail service**. Escalate to hosting/network owner and retain safe fail-closed user messaging.

**Exit evidence:** hosting policy accepted; DNS/ports/PTR verified; threat model, rollback and one clean synthetic transport test.

### MAIL-01 — P0 self-hosted transactional email (registration first)

- Self-managed **MTA/SMTP submission stack**, using vetted open-source software and standardized MIME/TLS/DKIM. Select and audit component licenses/support/security updates; candidates include Postfix, OpenDKIM, Rspamd and a dedicated restricted service account as applicable.
- Provider-independent internal `MailTransport` adapter from Main Platform; no log/array-only success and no `smtp → log` failover. Idempotent outbox, bounded retry/backoff, dead-letter/bounce/complaint registry, per-recipient rate limits, allowlists for initial validation, monitoring.
- SPF + DKIM + DMARC alignment and correct reverse/forward DNS; safe sending host identity; outbound-only service until mailbox requirements demand inbound service. Never expose production `APP_KEY`, SMTP credentials, or signed verification links in logs.
- **Production incident #391:** current live Laravel at `/home/kmjprod/current/apps/platform` reports `APP_ENV=production`, `APP_URL=kmjtechno.com`, `MAIL_MAILER=log`, `QUEUE_CONNECTION=database`; these accounts cannot receive messages. Until transport is truly configured, keep honest unavailability/registration fail-closed behavior (draft PR #390).
- Send ONE owner-authorized verification message, confirm outbound MTA acceptance **and recipient inbox arrival**, click signed HTTPS token to verify the intended account, test expiry/replay and password reset. Do not conflate `SMTP 250 queued` with final inbox delivery; collect explicit evidence.

**Exit evidence:** observable queue/retry/bounce paths, 1+ authorized real inbox deliveries and signed verification, no third-party email API requirement, production rollback rehearsed. **No assertion that this is currently done.**

### MAIL-02 — Secure staff mailboxes / inbound mail

- Secure mailbox storage, POP/IMAP/JMAP where justified, SMTP submission/auth, addresses/aliases/groups, MIME/attachment limits, spam/malware quarantine and contact rules; consider vetted Dovecot and standards-supported clients.
- First-party minimal webmail: compose, read, attachments, threads, search, folders/labels, contacts, drafts, smart filters, templates and signatures; deliverability/abuse admin dashboard.
- Encrypted transport, mail-store access controls, tenant isolation, quota enforcement, backups with tested restore, account lifecycle, audit, breach containment and migration/import/export.

**Exit evidence:** round-trip external send/receive, multiple common recipient providers, staff access control, restoration from backup, login/hardware security tests and operational alerts.

### MAIL-03 — Premium collaboration and enterprise workflows

Shared inboxes, delegated team inboxes, routing/rules, contacts/calendar interoperability, templated communications, role-sensitive knowledge, international localization, cross-device sync, offline drafting, mobile-ready versioned API and audited admin.

**Exit evidence:** measured user tasks, accessibility/keyboard speed, concurrency/isolation, complaint handling, SLA targets grounded in real monitoring.

### MAIL-04 — Privacy-first KMJ intelligence

AI summaries, priority inbox, semantic search, multilingual drafts/translation, action/meeting extraction, business workflows, fraud/phishing assistance. AI must be optional, transparent, consented and never bypass send approvals. AI-generated sensitive content must not be silently submitted to unknown paid/cloud endpoints.

**Exit evidence:** opt-out path, false-positive/quality evaluation, encrypted index and data-residency tests, security review of prompt/data injection and human approval before sending.

### MAIL-05 — Mobile and world-class qualification

Native/secure mobile companion or responsive PWA depending on verified needs; push delivery, controlled notifications, secure device pairing, offline drafts, sync and search. Stress tests, warmup/reputation, recovery/soak, deliverability benchmarks across Gmail/Outlook/Yahoo and representative corporate domains; global latency, accessibility, security response, spam and user experience studies.

**Exit evidence:** independent client feedback and benchmark data. Do **not** claim “better than Gmail” universally without clear chosen criteria, measured accuracy/usability/performance, security review and actual delivery evidence.

## 4. Security and operational policies

- Enforce SMTP AUTH, TLS validation, SPF/DKIM/DMARC, anti-spoof checks, inbound scanning, strict egress policies, open-relay prevention, per-account send quotas, bounce/complaint suppression, trusted forwarding, retention and incident response.
- Avoid unsolicited/mass campaigns, bulk sends from fresh IPs or domain/IP reputation manipulation. Set deliverability warm-up slowly for legitimate opt-in mail only.
- Separate outbound transactional sender reputation from future staff/customer high-volume traffic where infrastructure permits.
- Restrict AI to explicitly authorized decrypted content; default no training on customer mail, redact and minimize tool context, hard per-tenant trust separation.
- Maintain secrets in a protected store with rotation and no echoing to logs/chat. Recover via encrypted offsite backups, proven restore and idempotent reconciliations.

## 5. Existing implementation inventory (verified 13 Oct 2026)

- **Main Platform master roadmap V1.0:** no dedicated KMJ Mail product milestone yet; email appears only as `provider_boundaries.email: adapters_only`.
- **CloudOS `src/services/mail/provider.py`:** data types and a `NotConfiguredMailProvider` that explicitly returns NOT_CONFIGURED. It **does not send mail**.
- **CloudOS `src/services/mail/dispatcher.py`:** persists a bounded/idempotent JSON outbox, calling an injected provider. Current default is NOT_CONFIGURED. The current file persists recipient, subject and body in plaintext JSON protected by file permissions, **not verified encrypted**; harden retention/encryption before real customer use.
- **CloudOS `tests/test_mail_provider.py`:** synthetic mock-provider passing/recording tests, NOT live SMTP, DKIM, inbox-delivery or provider reputation certification. Existing `MAIL-001_PASS.json` is not evidence of live mail delivery.
- **Main Platform production:** owner-verified Laravel mailer LOG on actual live website, see issue #391. Registration verification is **currently broken** until a valid self-hosted external mail transport is accepted and deployed.

## 6. Priority policy

- **Immediate P0:** MAIL-00 feasibility, followed by MAIL-01 solely to unblock registration/password reset with correct sending and safe monitoring. This shall not wait for a full mailbox UI.
- **Product roadmap:** MAIL-02 onward remain **future planned phases** and must not displace immediate Main Platform commerce/security release or active KMJ product engineering without a revised owner-approved priority.
- Document is a reviewed **scope proposal**, not a service deployment request. No DNS/rDNS, mail ports, firewall, paid plan, VPS MTA, credentials, email accounts, production configuration or user mailbox data changed by this document.
