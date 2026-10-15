# KMJ Mail P0 — Temporary Brevo Free SMTP adapter

**Goal:** Unblock existing KMJ TECHNO registration, verification and password-reset notifications without waiting for the hosting provider's reverse-DNS repair. This is a **temporary external outbound-only delivery transport**, not the KMJ Mail product or a third-party mailbox dependency.

**Status:** Source integration only. NOT enabled on the live server. No confirmed sender-domain authentication, credentials, email acceptance, inbox delivery, or signed-token verification.

## Free-plan and authority constraints

- Brevo Free currently lists **300 total sends/day** and supports transactional mail. Do not add a card, select a paid subscription, enable pay-as-you-go, or assume a higher free limit. Limit exhaustion can delay transactional email; monitor sends, retries and expiration.
- **One organization-owned Brevo Free account is needed**; account sign-up and identity/security prompts are owner-only actions.
- Authorize the exact sending domain `kmjtechno.com` in Brevo. Brevo's Domain settings provide **specific** verification/DKIM records; do NOT guess or overwrite existing `kmj2026._domainkey` or `_dmarc`, and never replace the existing Cloudflare Email Routing MX.
- Brevo SMTP must be enabled for the account. Use its `SMTP login` plus **SMTP key** (not a REST/API key). Do not send keys by chat/email or commit to GitHub.
- If Brevo needs DNS records, request review of the public record names/types/values separately. Create only confirmed nonconflicting records in the `kmjtechno.com` Cloudflare zone.
- Keep DKIM aligned for the actual `MAIL_FROM_ADDRESS=no-reply@kmjtechno.com` (or another approved account-owned sender). Do not claim domain verification merely because the older KMJ self-hosted selector exists.

## App adapter (safe before account provisioning)

`apps/platform/config/mail.php` includes a named `kmj_brevo` SMTP mailer:

- SMTP host: `smtp-relay.brevo.com`
- Encrypted submission: `smtps` on port **465**, mandatory implicit TLS, not port 25; Brevo documents encrypted port 465. If network blocks 465, do not silently switch to opportunistic/plaintext SMTP: review a strict STARTTLS 587 configuration before use.
- Private environment: `KMJ_BREVO_SMTP_LOGIN`, `KMJ_BREVO_SMTP_KEY`, and explicit `KMJ_BREVO_ACTIVATED`; no credentials in source code or logs.
- `MAIL_MAILER=log` remains the default. Do NOT activate the named mailer until a valid and secure staged transport acceptance test and real owner-authorized inbox arrival.
- `RegistrationMailReadiness` fails closed when approval, valid login/key, aligned From domain or encrypted mode are missing. This is **configuration-readiness only**, never delivery proof.

## Acceptance/activation (production change is separate)

1. Owner creates **Brevo Free** account and completes any verification/SMPP activation.
2. Brevo authenticates the KMJ sending domain using nonconflicting DNS and verifies the selected From address. Retain current SPF and inbound MX/aliases.
3. An authorized operator securely provisions SMTP credentials in the **private production runtime secret configuration**, file permissions restricted. Never publish the key or pass it in shell arguments.
4. In an isolated staged Laravel environment, configure `MAIL_MAILER=kmj_brevo` and `KMJ_BREVO_ACTIVATED=true`, reload config and the queue worker using the existing guarded deploy system. Verify SMTP TLS certificate, remote relay acceptance and **actual owner-controlled inbox arrival**, followed by signed HTTPS verification/password reset; distinguish SMTP 250 from inbox proof. Keep the user production mailer `log` until this succeeds.
5. Once exact-head PR #423 source QA, deployment backup/rollback, owner acceptance and staged real-mail checks pass, activate the same **reviewed** config in production with bounded volume. No live sends before these gates.
6. Monitor queue/failed jobs, 4xx throttling, suppression/bounces, provider free quota, old-link expiry and signup/resend abuse. If delivery or verification regresses, restore previous known-good app mailer and code immediately; don't fake verification or mark an email as delivered.
7. In parallel, complete self-hosted MAIL-00/MAIL-01: Webyne PTR and outbound port 25 approval. Once the KMJ-owned MTA has independent real inbox acceptance and warmed reputation, change only the mailer selection to self-hosted `smtp`; keep the KMJ business/identity layer independent.

## Safe operator read-only check

`php artisan kmj:mail:doctor --json` reports whether an external delivery **attempt** is configured, without revealing credentials and without claiming delivery. Its `live_delivery_proven` must remain false until real acceptance evidence is recorded separately.

## Source evidence

- Brevo Free: https://help.brevo.com/hc/en-us/articles/208589409-About-Brevo-s-pricing-plans
- Brevo SMTP settings: https://developers.brevo.com/docs/smtp-integration
- SMTP key management: https://help.brevo.com/hc/en-us/articles/7959631848850-Create-and-manage-your-SMTP-keys
- Domain authentication: https://help.brevo.com/hc/en-us/articles/12163873383186-Authenticate-your-domain-with-Brevo-Brevo-code-DKIM-DMARC
- P0 issue: #391; self-hosted roadmap: #394; source PR: #423.
