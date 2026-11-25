# KMJ inbound pilot — source foundation, default OFF

Issue #1018. This branch establishes a signed ingress boundary and encrypted durable quarantine, not live inbound email or a published Inbox message.

- Scope: one proposed pilot recipient, mail-pilot@kmjtechno.com; not the current info@ route. No MX, routing or outbound configuration changes.
- A Cloudflare Email Worker forwards bounded raw MIME (up to 256 KiB) over HTTPS to the fixed Elite intake URL. HMAC-SHA256 binds version, UUID, timestamp, envelope recipient, envelope sender and SHA256 of raw bytes. Reject stale or invalid signatures. The shared random 32-byte secret is independently provisioned through protected environment and Worker secret binding, never GitHub or chat.
- Receiver defaults OFF. A configured owner ID must identify a currently verified passkey Platform Owner. Do not infer owner from sender or caller input. Lock owner record, deduplicate the signed event and byte-identical raw MIME per recipient, and cap intake at 100 per rolling day and 1000 retained messages. Envelope sender and full MIME are encrypted using Laravel encryption before storage. Receipt only means quarantine.
- MIME is not executed, rendered, attached to the existing mail records or forwarded to an AI provider. The signature authenticates ingress, not the sender's DMARC or trust status.
- Do not deploy or route mail until independent security review, retention and owner-account deletion policy review, storage/key backup plus recovery tests, exact CI and approved Elite staging. At ingress add bounded request body and rate limits; prove no payload or signature logging. Verify Worker error paths and actual SMTP failure handling in an isolated test.
- Next implementation: trusted MIME parser, plain-text sanitization, attachment quarantine and scanner, sender authentication classification, separate external sender identity (no fabricated KMJ user), per-mailbox recipient authorization, explicit release from quarantine to Inbox, secure reply threading, retention and audit. Do not claim receive UI readiness until real externally sent mail appears in authenticated Inbox.
- Do not enable the pilot by changing a production environment or Cloudflare routing until owner-approved end-to-end acceptance. Preserve current info@ forwarding; avoid any Gmail OAuth, Google VPS or paid service.

Cloudflare API reference: https://developers.cloudflare.com/email-service/api/route-emails/email-handler/
