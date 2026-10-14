# KMJ Mail MAIL-00 / MAIL-01 — Controlled Production Activation

**P0 incident:** #391. **Starting operator evidence (2026-10-14):** effective Laravel `mail.default=log`, `transport=log`, `queue.default=database`, configured From address valid; database worker active. Postfix inactive. Outbound TCP/25 reached one Google MX host; this is NOT inbox delivery proof. Existing Cloudflare Email Routing MX and SPF must be retained.

## Order of operations (NO live sending before readiness)

1. On KMJ-elite, confirm outbound public IPv4 independently; compare with sending egress path. Check provider's *written* anti-spam/outbound-SMTP permission, 25 limits, static IP and PTR control. No provider permission = BLOCKED.
2. DNS-only (not proxied) A record: `mail.kmjtechno.com` -> **verified SMTP egress IPv4**. Provider-set PTR for that SAME IP -> `mail.kmjtechno.com`. Check forward A and PTR agree.
3. Prepare DKIM public TXT without starting SMTP using `scripts/operations/kmj-mail-00-prepare-dkim.sh` as root. It generates and retains a private 2048-bit RSA key only in `/etc/opendkim/keys/kmjtechno.com/` and displays the corresponding public DNS value. **Never copy the private PEM into GitHub, chat, or Cloudflare**. Later, after host policy and DNS pass, use `scripts/operations/kmj-mail-01-bootstrap.sh` on Ubuntu 24.04 as root. It installs open-source Postfix/OpenDKIM, backs up configs, reuses the private key, binds loopback SMTP only, and leaves Laravel untouched.
4. Publish the exact generated **public** DKIM record as TXT at `kmj2026._domainkey.kmjtechno.com`. DNS TXT values may be split into quoted chunks; ensure the full `p=` key is unchanged. Validate with `opendkim-testkey`; DO NOT send email on DNS record presence alone.
5. Edit the EXISTING root SPF record; do not create two SPF records. Expected shape: `v=spf1 ip4:<ACTUAL_EGRESS_IPV4> include:_spf.mx.cloudflare.net ~all`. Keep current Cloudflare MX records and other verified senders. `_dmarc.kmjtechno.com` currently has `v=DMARC1; p=none;`; monitoring mode is acceptable during initial validation.
6. Enable Cloudflare Email Routing aliases or another actively monitored inbound path for bounce, postmaster and abuse addresses. A non-reply address must not silently swallow bounces. Design an explicit bounce/deferred/suppression workflow before customer-scale sending.
7. Run `MAIL_PUBLIC_IPV4=<VERIFIED_IP> MAIL_HOST_POLICY_APPROVED=yes bash scripts/operations/kmj-mail-00-readiness.sh`. This reports DNS/policy indicators but does not validate local DKIM key match or remote inbox delivery.
8. Confirm `systemctl is-active postfix opendkim`, `ss -ltn '( sport = :25 )'` shows only `127.0.0.1:25`, `postfix check`, `opendkim-testkey -d kmjtechno.com -s kmj2026 -k /etc/opendkim/keys/kmjtechno.com/kmj2026.private -vvv` (redact logs) and open-relay test from outside. If any test fails, DO NOT switch Laravel.
9. With production backup/rollback available and approved staged tests, set Laravel production environment **privately** to: `MAIL_MAILER=smtp`, `MAIL_HOST=127.0.0.1`, `MAIL_PORT=25`, `MAIL_FROM_ADDRESS=no-reply@kmjtechno.com`, `MAIL_FROM_NAME=KMJ TECHNO`; clear any obsolete `MAIL_URL`/`MAIL_SCHEME` overrides; use no SMTP credentials for a loopback-only listener. **Do not post the entire .env**. Keep existing `QUEUE_CONNECTION=database`. Rebuild config cache and restart worker/PHP-FPM via existing verified release procedure.
10. Use `php artisan kmj:mail:doctor --json`. This checks whether a delivery attempt can be made, NOT inbox receipt. Test exactly one owner-authorized new registration to a real inbox, request/resend throttle, HTTPS signed verification, correct-account identity, expiry, password reset, post-verification login and organization isolation. Confirm recipient inbox arrival; do not treat Postfix `250 queued` as delivered.
11. Monitor bounded queue/error/deferred/bounce events (redact signed URLs, recipient addresses and credentials in incident reports). Stage low-volume warm-up, idempotency and rate limits before public exposure. If anything regresses, restore previous Laravel mail environment/config and code symlink; preserve backups and logs securely. Do not bypass verification or update `email_verified_at` manually.

## Operator read-only commands

```bash
# Independently verify this is SMTP egress IP before DNS changes.
curl -4fsS --max-time 8 https://api.ipify.org; echo
dig +short A mail.kmjtechno.com
dig +short -x <VERIFIED_PUBLIC_IPV4>
dig +short TXT kmjtechno.com
dig +short TXT kmj2026._domainkey.kmjtechno.com
dig +short TXT _dmarc.kmjtechno.com
```

## Installation / rollback constraints

- Bootstrap is **not** production acceptance and must not be run on unreviewed shared mail hosts. Installation modifies system packages and MTA configs, never production Laravel secrets or user accounts.
- Exact reviewed branch installer: `scripts/operations/kmj-mail-01-bootstrap.sh`. It requires `MAIL_BOOTSTRAP_APPROVED=yes MAIL_HOST_POLICY_APPROVED=yes MAIL_DNS_AND_PTR_VERIFIED=yes` **after independently verifying those conditions** and writes backups under `/var/backups/kmj-mail/`. Until then, only the separate DKIM preparation script is eligible for execution.
- If an existing OpenDKIM multi-key configuration is detected, bootstrap stops rather than replacing shared signing maps.
- Restoring backed-up Postfix/OpenDKIM configs after package installation requires a scoped maintenance action. Test rollback on staging before customer rollout.
- The MAIL-01 installer is a **minimal secure sender foundation**, not a production-grade bounce/complaint registry or a complete Gmail-class mailbox implementation. These remain required before incident #391 may be closed at scale.

**Exit criterion:** provider policy accepted, precise egress IPv4 and matching DNS/PTR, correct DKIM SPF DMARC, controlled MTA, safe queue/error handling, real authorized inbox delivery and signed verification, exact-head CI green, release backup/restore and rollback verified. Until then: P0 NOT DONE.
