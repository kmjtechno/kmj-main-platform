# KMJ Mail: independent enterprise mail architecture (2026-11-22)

Status: **design + guarded first code change**, **NOT live or fully tested**. Source of truth for implementation remains actual GitHub commits, CI and on-host runtime evidence. No Gmail OAuth, Google VPS, new paid services, DNS/MX cutover or blind resend.

## Current architecture and P0 incident

- KMJ Main Platform (Laravel 13, PHP 8.4, PostgreSQL) has authenticated owner/staff internal mail, external compose, durable queued jobs, owner-granted sender aliases and quota/idempotency safeguards.
- Postfix + OpenDKIM on KMJ-elite handle Internet outbound; the old transactional `sendmail` transport must remain untouched by this feature branch.
- Existing native outbound job used `/usr/sbin/sendmail -t -i`; this spawned `postdrop`. The production queue systemd unit has `NoNewPrivileges=yes`; the live postdrop child inherited `NoNewPrivs:1` and effective GID 1000 rather than required group postdrop GID 125. `mail_queue_enter` logged 295 permission-denied failures and the PHP worker hung in `pipe_read`.
- Mail message ID1 is `submitting` (uncertain, NEVER blindly resend), ID2 remains `queued`. A Nov 21 deferred Postfix queue entry is older than both. The precise outcomes need reconciliation without duplicate submission.
- P0 incident issue: https://github.com/kmjtechno/kmj-main-platform/issues/1029

## P0 bounded local SMTP adapter

Keep `NoNewPrivileges=yes` and the Postfix spool permissions unchanged. Use **Symfony/Laravel SMTP over pinned TCP 127.0.0.1:25**, avoiding a setgid postdrop subprocess inside the sandboxed worker.

1. The `kmj_native_loopback` mailer has immutable host `127.0.0.1`, port `25`, no authentication secrets, no caller-controlled DSN or fallback and explicit `timeout=8` seconds. It is ONLY for native owner/staff external mail.
2. Independent `KMJ_NATIVE_EXTERNAL_MAIL_TRANSPORT=loopback_smtp` must be explicitly owner-set. Its default is `disabled`, including when the earlier `KMJ_NATIVE_EXTERNAL_MAIL_ENABLED=true` survives. This deliberately fails closed on first deployment.
3. The native mailer's transportEnabled guard checks the fixed values. It must not inherit the app's transactional `MAIL_MAILER` transport for message submission. Sender identity, quotas, actor permission, idempotency and `$tries=1` no-automatic-retry remain.
4. `mta_accepted` means the local SMTP server responded successfully, **never** proof of delivery to recipient. A transport timeout can mean unknown handoff; do not automatically resend any `submitting` message.
5. No deployment or activation until the existing stuck worker/job1/postdrop process and old maildrop state are safely reconciled.

### Required owner-run READ-ONLY preflight (Elite)

```bash
systemctl show kmj-main-platform-queue.service -p NoNewPrivileges -p User -p MainPID
postconf -h inet_interfaces
postconf -h mynetworks
postconf -h smtpd_relay_restrictions
postconf -h smtpd_recipient_restrictions
ss -H -ltn '( sport = :25 )'
php8.4 -r '$e=0;$s=@stream_socket_client("tcp://127.0.0.1:25",$e,$m,1);echo $s?"LOOPBACK_SMTP=REACHABLE\n":"LOOPBACK_SMTP=BLOCKED\n"; if($s)fclose($s);'
```

Verify listener is **local and secured against unauthorized relay**. `ss` listener or a successful TCP connect alone does NOT prove relay safety, Postfix delivery, DKIM signing or Gmail receipt. Do not open anonymous SMTP on a public interface or add broad `mynetworks` entries. Existing public Postfix bindings may be necessary for current operations; never change them without independent review.

### Guarded rollout / reconciliation

1. CI exact-head tests green; review mailer config, transport gate, codeowners and release helper pin. GitHub PR merged only through normal rules.
2. Owner confirms Postfix loopback SMTP reachable and appropriate relay restrictions; inspect affected `postdrop` process, Postfix maildrop/deferred queue and timestamps; archive redacted receipts.
3. Preserve ID1 `submitting` for manual reconciliation, **never** requeue or automatically mark accepted. Preserve pending ID2. Do not clear queues or kill systemd worker before approving controlled recovery.
4. Owner executes the normal Elite SHA-pinned release path and root approval (no bypass). On cutover, the **new** transport remains OFF unless specifically enabled.
5. Only after step 2 and job1 reconciliation, owner sets both `KMJ_NATIVE_EXTERNAL_MAIL_ENABLED=true` and `KMJ_NATIVE_EXTERNAL_MAIL_TRANSPORT=loopback_smtp` in protected production env, rebuilds Laravel config cache, coordinates a single controlled worker restart.
6. Verify ID2 processes **once** without duplicate ID1; use a new owner-controlled test only when the original queue is safe. Independently verify app status, Postfix accepted/deferred/bounced and recipient inbox authentication headers.
7. On failed verification, keep native external sends disabled. Do not change MX, SPF, DKIM, DMARC, owner approval, signers or backup policy as a workaround.

## P1-P3 road map (planned, not implemented by this PR)

### P1 — True inbound mail, no customer-facing Gmail account connection
- Preserve current Cloudflare Email Routing MX until signed, audited inbound pipeline is tested; no unreviewed cutover.
- Design recipient domain/address verification, authenticated and idempotent inbound transport, controlled attachments, malicious MIME/HTML sanitization, phishing/spam classification, per-mailbox isolation, quarantine, virus scanning and bounce handling.
- Do not expose a public open relay. All inbound messages need event IDs, signatures/validated origin, replay limits, retention and redacted logs. A staged local Postfix receiver or Cloudflare Worker-to-Elite signed ingest are alternatives, not yet selected.

### P2 — JMAP-compatible API and real-time mailbox UX
- Implement mailbox/identity/thread/labels/flags in the existing backend first. Keep a stable per-mailbox state token and incremental change events, per-user authorization and RFC-aware threading.
- Only call it **JMAP-compliant** after interoperability testing against RFC 8620 + RFC 8621; WebSocket transport per RFC 8887 is an optional later module.
- Inbox, Sent, Drafts, Trash, Spam, archive, folder search, conversation history, pagination, optimized attachment handling, unread counts, and accessible responsive design. Avoid loading full mailbox contents into the first page.
- Per-device sessions, role-based staff access, owner-managed aliases, immutable audit receipts and tenant isolation.

### P3 — Enterprise deliverability and resilience
- SPF/DKIM alignment, DMARC **RFC 9989 (May 2026)**; gradual DMARC policy hardening only after aggregate report review. Optional MTA-STS/TLS reporting after verifying actual inbound MX and service configuration.
- Structured state machine: `queued → submitting → mta_accepted → downstream_deferred | bounced | verified_delivered`, with `submitting_unknown` reconciliation path. Exact-once **submission attempts** can be guarded locally; Internet email delivery cannot promise global exactly-once.
- MTA queue-ID correlation, DSNs, signed bounce sources, complaint handling, alerts, metrics, rate controls and circuit breakers. Never mislabel MTA acceptance as recipient receipt.
- Anti-abuse throttles, attachment limits and object encryption, secure headers, CSRF/authorization, audit/no PII leaks, tests simulating blocked subprocesses, unavailable SMTP, delayed acknowledgements and process crashes.
- Keep signing keys, backups, owner release approvals and infrastructure owner-managed on Elite; external transport requires explicit owner approval.

## References
- Symfony Mailer: https://symfony.com/doc/current/mailer.html
- Postfix relay restrictions: https://www.postfix.org/BASIC_CONFIGURATION_README.html
- JMAP Core / Mail: https://www.rfc-editor.org/rfc/rfc8620.html and https://www.rfc-editor.org/rfc/rfc8621.html
- JMAP WebSocket: https://www.rfc-editor.org/rfc/rfc8887.html
- DMARC (2026): https://www.rfc-editor.org/rfc/rfc9989.html
