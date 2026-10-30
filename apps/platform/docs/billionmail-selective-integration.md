# BillionMail selective integration — KMJ Main Platform

**Status:** Source-only, disabled by default. No container or SMTP listener
installed. Production DNS, MX, Cloudflare routing and mail remain unchanged.

## Chosen parts

- Use BillionMail as an **optional isolated mail service** for authenticated transactional SMTP submission (SMTPS/465), keeping KMJ's current Laravel notifications, signed verification/reset links, and sender-domain gate.
- If an isolated pilot proves itself, evaluate BillionMail's **delivery/bounce/queue analytics** and API for **consent-based** newsletters. Explicitly separate marketing mail from critical OTP/verification traffic and rate-limit both.
- Keep **Brevo** as an individually verified alternative, not an unvalidated failover that reports success when nothing reached an inbox.
- Preserve **PostgreSQL** in the Main Platform. Any BillionMail PostgreSQL/Redis stores must be isolated and separately backed up; do not share application databases or import mail-server tables into KMJ.
- Reuse concepts/integration boundaries, not upstream AGPLv3 source directly in proprietary platform code. Conduct AGPL obligations review for any modifications/network-hosted deployment.

## Excluded deliberately

Do not copy its complete management dashboard, customer identity system, mailbox/provisioning stack, Roundcube webmail, spam policy UI, or replace existing KMJ admin/marketing surfaces. Do not activate open signup, mass sending, tracking pixels, link tracking, or external API access by default.

## Safe deployment gates (not yet completed)

1. Confirm current primary SMTP live delivery results, host resources, ports already in use, signed production release/rollback gates, and offsite recoverability **read-only**. Existing nginx 80/443 and mail 25/465/587 may conflict with the upstream Docker defaults.
2. Stage BillionMail separately with pinned, audited images, private firewall rules, no public admin panel or default passwords, least privilege, reviewed Docker socket exposure, and bounded CPU, RAM and disk. Use a dedicated host if same-host conflicts or resources are unsafe.
3. Verify protected inbound MX/Cloudflare routing for `info@kmjtechno.com` remains unchanged. For outbound: authenticate domain with DKIM/SPF/DMARC, verify accurate EHLO/PTR/rDNS/forward DNS and reputation, and confirm provider allows outbound TCP 25 or verified authenticated relay. The software **cannot** fix a Gmail 550 5.7.1 authorization rejection on its own.
4. Provision a private SMTPS/465 endpoint with a trusted certificate that matches `KMJ_BILLIONMAIL_SMTP_HOST`, authenticated credentials and relay restrictions; refuse insecure fallback. Put credentials only in private deployment secrets, never Git/issue comments/logs.
5. Keep `KMJ_BILLIONMAIL_ACTIVATED=false` and `MAIL_MAILER=log` until security review, dry-run, authorized delivery to Gmail/Outlook, bounce/queue checks, backup and rollback PASS. Start with low-volume transactional tests.
6. Once externally approved, privately set `KMJ_BILLIONMAIL_SMTP_HOST`, `KMJ_BILLIONMAIL_SMTP_LOGIN`, `KMJ_BILLIONMAIL_SMTP_PASSWORD`, `MAIL_FROM_ADDRESS`, `KMJ_BILLIONMAIL_ACTIVATED=true`, and `MAIL_MAILER=kmj_billionmail`. These are operator steps, not instructions to enable automatically.
7. Confirm a real user can receive and use verification/reset email before enabling registration. Monitor sanitized SMTP accept/reject counts, bounces, queue depth, and abuse/complaint rates. Mailer readiness checks only mean *configured for an attempt*, **not** delivered.
8. Build marketing integration only after owner-only UI authorization, verified opt-in, suppression/unsubscribe support, rate/recipient caps, retention/privacy compliance, and separate transactional priority.

## Licensing and ownership

Upstream: https://github.com/Billionmail/BillionMail (AGPLv3, review current tagged release and its transitive dependencies). Do not vendor or merge the upstream software into KMJ's Main Platform until licensing/security review. Optional standalone network deployment is a separate decision.

## Configuration interface

The new named Laravel mailer is `kmj_billionmail` in `config/mail.php`. The existing `RegistrationMailReadiness` checks explicit activation, sender domain, credential shape, implicit TLS and port 465 before permitting a delivery attempt. **No** credentials or service URLs are baked into production configuration.

## Verification

Targeted tests: `php artisan test --filter=BillionMailTransportTest` in a disposable, dependency-complete development environment, plus existing `BrandedAuthMailTest`, `RegistrationTest`, and `EmailVerificationTest`. CI and real-inbox delivery must be confirmed independently before merge/cutover.
