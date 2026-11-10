# KMJ TECHNO — zero-additional-cost transactional email recovery

**Status: diagnostic candidate only; no live sending is claimed.**
**Protect production:** do not change Webyne VPS IP, DNS/MX, Cloudflare Email Routing,
Posta credentials, the deployed Laravel mailer, or existing customers from this runbook.

## Facts checked on 19 October 2026

- The KMJ account's Cloudflare Email Routing is enabled and has two verified
  destination addresses. This is inbound forwarding, not customer outbound SMTP.
- Cloudflare Email Sending Beta on Workers Free can send only to verified
  destination addresses. Sending to arbitrary newly registered customers
  requires Workers Paid. Do not upgrade on the owner's zero-extra-cost budget.
  Source: https://developers.cloudflare.com/email-service/platform/pricing/
- goposta/posta v0.17.0 is a self-hosted mail API, queue and SMTP relay.
  Posta needs a working SMTP outbound provider or permitted direct-MX sending.
  A queued result does not prove actual recipient delivery.
  Source: https://github.com/goposta/posta
- An earlier Posta installer attempt lacked Docker. A later claim of installation
  cannot be considered independently verified runtime evidence. CodeBridge
  project-scoped tools do not expose arbitrary host-service inspection.
- Webyne ticket VQA-978224 for 103.212.136.154 PTR and outbound SMTP permission
  lacks provider confirmation in the latest accessible correspondence.
- Laravel currently has a disabled-by-default, credential-gated kmj_brevo SMTPS
  adapter (port 465) in apps/platform/config/mail.php. This is an option,
  not proof of an approved free account or functioning delivery.
- Preserve fail-closed signup and verified-only authenticated/product routes.

## Read-only one-command preflight

On the authorized VPS, from a clean checkout with this script:

    bash scripts/operations/kmj-mail-zero-cost-preflight.sh

Optional actual deployed Laravel app path (no secrets):

    KMJ_MAIL_APP_ROOT=/home/kmjprod/current/apps/platform bash scripts/operations/kmj-mail-zero-cost-preflight.sh

The script does NOT send mail, read secrets, restart services, create accounts,
edit DNS, or modify files. It checks A/PTR resolution, Docker/Posta commands,
loopback ports 9000/2526, worker-process hint, and the secret-free Laravel mail
doctor. Missing observations remain NOT_VERIFIED, not PASS.

## Choose one authorized outgoing transport

**Temporary free relay:** If an existing SMTP relay account (for example Brevo
Free, subject to current plan, sender-domain verification and account approval)
is available, place its credential only in the existing protected production
secret mechanism. Use verified KMJ domain sender, enforced TLS, quotas and
suppression handling. The existing kmj_brevo adapter is explicit opt-in. Never
paste SMTP keys in GitHub, ChatGPT, logs or issue comments. Do not activate until
one consented recipient's real inbox and link-validation tests have passed.

**Self-hosted preferred:** If Webyne confirms valid PTR, stable SMTP egress IP
and port-25 permission, verify Posta worker, outbound SMTP acceptance, domain
signing and actual inbox delivery. Keep the Posta management UI private and
replace any demo/default credentials. Do not overwrite Cloudflare MX records.

**Cloudflare:** Retain Email Routing and verified test destinations on Free.
This is not a free universal sender to unknown new customer addresses.

## Acceptance before real registrations

1. Verified provider and sender domain; no additional subscription expenses.
2. One user-consented external test inbox genuinely receives a message (not
   only SMTP 250, HTTP 202 or an enqueued Posta message).
3. HTTPS signed verification link confirms only intended user; expiration and
   resend throttling behave correctly; password reset delivers successfully.
4. Retry, timeout, bounce and queue worker behavior are checked; no silent
   fallback to Laravel log or array transports.
5. Exact-head auth regression, staging browser acceptance, backup/rollback and
   guarded production release approval all pass.

## Blockers still open

- Live Posta installation and worker/SMTP pipeline not independently verified.
- No approved SMTP relay credential is available to this development session.
- Webyne PTR and direct SMTP egress permission have no confirmed resolution.
- The reported 22 users require aggregate-only audit, not bulk deletion or
  unsolicited mail.
- GitHub code/PR and green CI are not proof of a production deployment.

Creating this diagnostic/runbook spends nothing and mutates no production state.
