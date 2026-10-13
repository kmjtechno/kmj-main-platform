# KMJ Main Platform — Registration verification email recovery

**P0 customer onboarding.** This is a deployment runbook, not a claim that SMTP delivery is already working.

## Evidence and root-cause checks

The application's development defaults are `MAIL_MAILER=log`, `MAIL_HOST=127.0.0.1`, `MAIL_PORT=2525`, `MAIL_FROM_ADDRESS=hello@example.com`. **Laravel's log and array mailers do not deliver to recipients.** The stock /email/verify green flash only reports that the send route returned; it is not an SMTP delivery receipt. Existing `VerificationNotificationTest` uses `Notification::fake()` and verifies dispatch, not inbox delivery.

This does not establish the live mailer configuration. Verify the *live deployed app* on the VPS rather than the repository checkout.

### Safe live diagnostic (never paste credentials)

From the **deployed** `apps/platform` directory (the one serving `kmjtechno.com`), run:

```bash
php artisan about --only=environment
php artisan kmj:mail:doctor --json
```

The second command is available after this patch is deployed. For the current older release, use this read-only alternative:

```bash
php artisan tinker --execute='echo "MAILER_TYPE=".config("mail.default").PHP_EOL; echo "TRANSPORT=".config("mail.mailers.".config("mail.default").".transport").PHP_EOL; echo "QUEUE_MODE=".config("queue.default").PHP_EOL; echo "FROM_CONFIGURED=".(filter_var(config("mail.from.address"), FILTER_VALIDATE_EMAIL) && strtolower(config("mail.from.address")) !== "hello@example.com" ? "yes" : "no").PHP_EOL;'
```

Do not print `config('mail')`, `env()`, passwords, token URLs, sender/recipient addresses, full exception stack traces, or raw `laravel.log`. When reviewing errors, share only **redacted** SMTP codes and timestamps.

### Fixing the actual transport

1. Choose a real authenticated SMTP service or transactional-mail provider, verify the sending domain and sender identity. Free quota may be possible, but verify the current provider plan before signing up; do not enable paid overages.
2. In the actual **production** environment (not Git), configure **`MAIL_MAILER=smtp`**, `MAIL_HOST`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_FROM_ADDRESS` and `MAIL_FROM_NAME` according to that provider's official instructions. Prefer STARTTLS on 587 or implicit TLS on 465 where supported. Use the correct provider sender domain. **Never share or commit credentials.**
3. Publish the provider's SPF and DKIM DNS records; set an appropriate DMARC policy after verifying valid alignment. DNS changes require authorized domain access and validation; do not replace unrelated MX, web or licensing records.
4. Only after staging verification and an approved maintenance window, clear/rebuild cached Laravel config on the deployed app using `php artisan config:clear && php artisan config:cache`. Check the active PHP-FPM process and reload it through the normal service deployment procedure, with rollback available. Do not alter production `APP_KEY`, database or encryption keys.
5. Send **one** test verification email to an address you own and have agreed to receive; confirm it arrives, link is valid/HTTPS, signature expires appropriately, clicking once verifies the *correct user*, and no account enumeration/duplicate unverified account occurs.
6. Check provider delivery dashboard for accepted/delivered/bounced/deferred status. SMTP accepted is not inbox delivery; if unavailable, check junk/spam, domain DNS alignment, queue worker health if using queued notifications, and provider suppression lists. Rate-limit resends; do not blast messages.
7. Re-run regression and auth HTTP tests on the exact build, verify other registration and password-reset emails, then monitor errors. Do not claim this P0 resolved before a real delivery/verification test.

### Patch behavior

- Production signup **fails before user/organization creation** when the mailer is log-only, array-only, unsafe failover or sample-local SMTP. This is deliberate fail-closed protection against accounts that cannot verify their email.
- New/verify screens display a clear warning when configured delivery is unavailable and avoid claiming an email reached the inbox. The verify page disables repeated resend attempts in that situation.
- Read-only `kmj:mail:doctor` reports safe transport type and whether a real delivery *attempt* is possible, without credentials or user data.
- Tests cover readiness, honest Inertia props and standard Fortify signed verification semantics. Existing verified users are not invalidated.

**Limitations:** Good configuration does not prove the SMTP connection succeeds, provider accepts the sender, DNS passes authentication, or the email lands in an inbox. Those require a live non-spam test after owner approves credentials.
