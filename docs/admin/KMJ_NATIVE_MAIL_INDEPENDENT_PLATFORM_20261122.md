# KMJ TECHNO — Independent Native Mail Workspace (No Gmail Integration)
**Owner direction 22 November 2026:** Build KMJ Mail as KMJ's own Gmail-class product, **not** an app connected to Google Gmail or to the owner's personal inbox.

## Implemented source-only private on-platform mail slice

- **Own storage and screens:** new `kmj_mail_messages` database-backed Inbox, Sent, Drafts and Trash, private thread history, read/unread, limited search, owner/staff compose, drafts, replies, idempotent internal delivery, and reversible per-mailbox trash.
- **Own internal staff IAM:** separate owner-approved `kmj_mail_staff` access ledger. It does **not** treat a customer organization `admin` or `member` role as KMJ internal employment. The Platform Owner remains passkey-verified, email-verified and `password.confirm` gated.
- **First-party URLs:** `/operator/mail` for owner, `/team/mail` for approved internal staff. No custom token exposed to browser, and staff cannot enter `/operator/mail` or grant their own privileges. Owner may grant/revoke an existing verified account by user ID through an audited action. Revocation immediately blocks staff access.
- **Internal delivery:** a committed DB transaction creates **one Sent copy in sender's mailbox and one Inbox copy in recipient's mailbox**. This is only a first-party KMJ internal message, *not* Internet SMTP, and the UI says so. Each mailbox sees only its own copies. Per-submission client UUID prevents sequential duplicate delivery; draft send uses DB row locking for idempotency.
- **Safe defaults:** no external sender/recipient entered, external SMTP sending is deliberately unavailable, no raw MIME attachments or HTML rendering, no Gmail OAuth, no imported mail history, no fabricated inbox rows, no migration of owner Gmail data, no new paid provider.
- **UI/UX:** locked KMJ logo and corporate charcoal/red shell, responsive three-pane layout, keyboard-readable controls, Compose/Reply, recipient chooser from verified KMJ staff and owner, thread view, search, drafts, Sent, Trash and owner-only staff manager. Existing premium HTML/text transactional templates remain available as a separate template gallery.
- **Audit:** staff grants/revocations and internal delivery recorded with IDs only; no secret, subject or body in audit metadata.

### Deployment and verification

This PR adds database tables. Run exact-head Laravel tests, Pint, PHPStan, TypeScript/frontend lint/build, PostgreSQL 18 forward migration/rollback tests, authorization cross-tenant negatives and independent browser QA. No database/production mutation is authorized by merging the PR. Deploy the reviewed SHA only from Elite with owner-signed approvals and the existing fast-release chain. Verify `CHAIN_EXIT=0` and actual mailbox behavior as one owner plus one explicit staff identity before declaring it LIVE.

## Internet email is a separate guarded acceptance stage

The company already controls the `kmjtechno.com` domain and has existing production **Postfix outbound** (Elite), **OpenDKIM**, **Cloudflare MX Email Routing** and a Postfix Brevo fallback. Preserve those until a carefully reviewed migration:

1. **Inbound without Gmail:** a Cloudflare Email Worker can receive a **new pilot address** for `kmjtechno.com` and deliver a signed, size-bounded HTTP envelope to an authenticated KMJ Elite ingest adapter. Cloudflare Email Routing supports Worker destinations on the free plan. Enforce HMAC/timestamp/nonce, domain/alias authorization, validation, deduplication, encrypted storage and attachment/AV policy. Do **not** switch `info@` away from the existing route or overwrite Cloudflare MX before independent tests and owner approval.
2. **Outbound to Internet:** controlled Postfix sendmail submission with domain-verified KMJ staff aliases; DKIM/SPF/DMARC, delivery-status capture, bounded per-user rate, logs redacted and bounce handling. Do not send external mail as another user's identity or treat a successful local queue submission as recipient delivery.
3. **Industrial trust features:** IMAP/SMTP standards compatibility may be added through independently audited, hardened mail services (e.g. Dovecot), without opening an unauthenticated external relay. Do not invent or expose ports/tokens. DNS/provider and mail server config changes require owner review.
4. **Mature product:** full-text indexing, threaded search, attachments with malware scanning and file quotas, spam filtering, scheduled send, labels/star/archive, retention/backup recovery, audit, calendar/contacts/tasks integrations, mobile push, accessibility and controlled delegated shared mailboxes. Only advertise each feature once implemented and tested.

## Hard boundaries

- **No Gmail connection, sync, OAuth or data import** into KMJ Mail.
- Do not confuse KMJ private internal messages with Internet-standard external email acceptance.
- Keep actual transactional account verification, password reset, orders and licenses mail in their existing approved Laravel/Postfix pathway; the internal staff mail UI does not alter or replace those.
- No auto staff grants, no unverified signup cleanup, no customer mailbox visibility, no automatic destructive user data deletion.
- Existing vendor email provider credentials, MX and external Gmail account remain untouched.
