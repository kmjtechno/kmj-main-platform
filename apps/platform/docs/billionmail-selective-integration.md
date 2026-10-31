# BillionMail integration boundary

**Status:** Source only. Disabled by default. No service was installed.

## Selected for KMJ

- Optional authenticated SMTPS/465 for transactional email.
- Existing Laravel verification and password reset flows.
- Private, opt-in configuration with a sender-domain gate.
- Brevo as a separately tested alternative transport.
- Later: sanitized delivery logs, bounce and queue analytics.
- Later: consent-based marketing with unsubscribe and rate limits.

## Not selected

- A second customer identity or permission system.
- Roundcube, new mailboxes or a duplicate admin dashboard.
- A new shared database or a replacement for KMJ PostgreSQL.
- Default tracking pixels, link tracking or bulk email sends.
- Replacing Cloudflare Email Routing or the existing MX records.

## Deployment gates

1. Inspect existing SMTP, nginx, ports, disk and backups read-only.
2. Audit images, privileges, Docker socket exposure and licenses.
3. Stage separately with private networking and safe resource limits.
4. Verify DNS, PTR, SPF, DKIM, DMARC and outbound acceptance.
5. Confirm SMTPS certificate, credentials and relay restrictions.
6. Verify authorized Gmail and Outlook inbox delivery and bounces.
7. Confirm queue behavior, backup restoration and rollback.
8. Activate only after the owner accepts all production gates.

## Configuration

- Named Laravel transport: `kmj_billionmail`.
- Activation flag: `KMJ_BILLIONMAIL_ACTIVATED=false`.
- Host: `KMJ_BILLIONMAIL_SMTP_HOST`.
- Login: `KMJ_BILLIONMAIL_SMTP_LOGIN`.
- Password: `KMJ_BILLIONMAIL_SMTP_PASSWORD`.
- Production mailer remains unchanged until a guarded cutover.
- Keep credentials in private server secrets, never in Git.
- Readiness means an attempt is possible, not that inbox delivery passed.

## Tests

- Run `php artisan test --filter=BillionMailTransportTest`.
- Re-run existing registration, verification and branded mail tests.
- Verify exact-head CI and isolated inbox QA before merging.

## License

Upstream: https://github.com/Billionmail/BillionMail

The upstream is AGPLv3. No upstream source was copied into KMJ.
Review obligations before deploying or modifying the separate service.
