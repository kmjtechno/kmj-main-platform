# KMJ Mail — Native Outbound Email To Gmail, Outlook and Any Address

**Owner request:** A real first-party KMJ TECHNO email product with a free-form recipient field; do not connect or sync personal Gmail. Source PR #1022.

## What this milestone adds

- **Compose modes:** type any *one* validated external email address (Gmail, Outlook, Yahoo, business or other) or choose a KMJ internal staff recipient. Existing private internal Inbox/Sent/Drafts/Trash still works.
- **Owner + approved staff:** the verified passkey Super Admin sends from the configured `@kmjtechno.com` company sender. KMJ staff must be explicitly granted a **unique** `@kmjtechno.com` sender alias through the owner staff-access panel. Staff cannot use `info@`, `support@`, `security@`, `admin@` or other reserved shared identities. Revoked staff are blocked before queued submission.
- **Actual server submission:** the `SubmitNativeExternalMail` queue worker uses **only** Laravel `sendmail` transport bound to the Elite VPS's existing local Postfix. It does not require OAuth, Google SMTP, Gmail API, an external SaaS mailbox, CloudOS or Google VPS.
- **Business-grade safety:** one recipient per message, 5/min external HTTP throttle, daily cap 20 owner / 5 staff, stable UUID idempotency, no client-selected FROM/CC/BCC, no script in emails (escaped HTML plus plain text), private copy in Sent, owner-granted aliases and bounded audits.
- **Delivery truth:** `queued`, `submitting` (unknown if interrupted), `mta_accepted`, `blocked`, `failed`. The acceptance means Postfix accepted a message, **not** that Gmail or another service delivered it to the Inbox. A crash after SMTP submission leaves `submitting` pending manual reconciliation, not an automatic duplicate send.
- **Drafts:** can save an external address/subject/body without activating the transport. Sending a draft requires the sender and transport gates.
- **Migration:** additive nullable sender/recipient/status fields on `kmj_mail_messages`; nullable unique staff alias on `kmj_mail_staff`. Existing internal messages remain intact. No user deletion or Gmail data import.

## Gated production release

The flag `KMJ_NATIVE_EXTERNAL_MAIL_ENABLED` is **FALSE by default**. The system reports `not_activated` and disables external Send until *all* checks are satisfied:

1. Exact-head GitHub CI PASS including full PHP/TypeScript, PostgreSQL 18 migration and rollback, security negative tests and owner/staff QA.
2. Owner signs and activates the **exact PR merge SHA** through fixed Elite-only release sequence. No stale predecessor or cross-agent approval.
3. Confirm `MAIL_MAILER=sendmail`, the exact /usr/sbin/sendmail -bs -i transport, configured `MAIL_FROM_ADDRESS` belongs to kmjtechno.com; queue service healthy and local Postfix/OpenDKIM available. `RegistrationMailReadiness::canAttemptDelivery()` is configuration only.
4. Independently verify SPF, DKIM and DMARC headers on a carefully **owner-authorized single email pilot** to one external inbox and document the recipient's actual receipt. Explicitly approve the sender alias and desired daily caps. Never auto-email unverified registrations, customers or contacts.
5. Enable `KMJ_NATIVE_EXTERNAL_MAIL_ENABLED=true` **on Elite only** as a distinct authorized production environment change, refresh Laravel cached configuration safely through the established guarded release or owner-approved procedure, inspect the UI status and queue receipt. Do not expose SMTP secrets.
6. Monitor queue failures and Postfix delivery/deferral/bounce separately. The UI must not claim external Inbox receipt on the basis of `mta_accepted`.

### Why the screen could previously only choose a colleague

The old `kmj_mail_messages` schema and `NativeMailController` only stored numeric internal user IDs and directly duplicated database messages into KMJ private inboxes. There was no external address, outbound queue or SMTP state. The new `recipient_type=external` path is separate from the internal path, so external recipients do not get mistaken for KMJ employees.

## Pending for full two-way Gmail-class service

Issue #1018 still covers receiving **Internet mail into KMJ Mail** without Google/Gmail: a scoped Cloudflare Email Worker pilot to a signed Elite HTTPS ingestion endpoint, MIME parsing, spam/AV quarantine, mailbox aliases, reply headers, inbound dedupe and backup/retention. Existing Cloudflare MX and `info@` forwarding remain unchanged until independently verified owner cutover. Other planned features: verified delivery/bounces, external reply threading, true IMAP/SMTP standards, contacts, labels/archive, attachment scanning, quotas, mobile notifications and search index. No unsupported feature may be labelled LIVE.
