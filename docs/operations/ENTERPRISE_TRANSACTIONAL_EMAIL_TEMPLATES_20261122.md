# KMJ TECHNO — premium transactional email system (22 Nov 2026)

**Scope:** Source-only feature branch. The existing Laravel signed verification/password reset notifications are already branded by `BrandedAuthNotifications` and **are not modified** here. This change adds a consistent enterprise transactional suite using the owner's actual `/assets/brand/kmj-email-lockup-dark.png` asset. It is not yet a live delivery acceptance receipt.

## Design contract

- Mobile-responsive, table-based HTML for Gmail, Outlook and most clients; accessible heading, visible high-contrast button, no external font/JS or tracking pixel.
- Exact locked KMJ black/graphite/red identity, left-aligned official logo and `INNOVATE | BUILD | SCALE`.
- First-party links only (`/dashboard`) and plain-text MIME alternative.
- Dynamic fields are Blade-escaped; subjects are static and never accept untrusted content; no caller-provided external CTA URL.
- Distinguish requested vs confirmed vs settled vs activated. A receipt is not a tax invoice, and an order is not a license.
- One support address, no marketing upsell, no unsubscribe links in strictly transactional notices.
- Signed verification and password-reset URL generation, expiry, auth checks and rate limiting stay in the existing Laravel implementation.

## Template matrix

| Trigger / template | Readiness | State requirement |
| --- | --- | --- |
| Email verification | Existing implementation | Signed Laravel verification route |
| Password reset | Existing implementation | Reset token and expiry |
| Welcome | Wired to first successful `Verified` event (opt-in) | Verified user |
| Order request received | Wired through idempotent commerce domain outbox (opt-in) | Persisted `requested` order |
| Order confirmed | Wired through commerce outbox (opt-in) | Persisted `confirmed` order |
| Payment receipt | Separate owner opt-in on confirmed-order outbox | Confirmed amount, ISO currency and provider reference |
| Payment not confirmed | Renderable but no automatic sender | Verified failed attempt, not a browser callback |
| Order cancelled | Wired through commerce outbox (opt-in) | Persisted `cancelled` order |
| License activated | Renderable but no automatic sender | Authorized issuance state `active` |
| Subscription renewal | Renderable but no automatic sender | Authoritative renewal state `renewed` |
| Security alert | Renderable but no automatic sender | Audited account security event |
| Support update | Renderable but no automatic sender | Authorized case status |

**Important:** Renderable means the message can be constructed and tested; it does not mean the corresponding domain event is configured to send mail. Do not wire new event types to untrusted or incomplete payment, licensing, subscription, or support workflows. Such integrations require separate end-to-end testing.

## Runtime integration and owner gates

1. Keep `KMJ_TRANSACTIONAL_NOTIFICATIONS_ENABLED=false` and `KMJ_TRANSACTIONAL_PAYMENT_RECEIPTS_ENABLED=false` until all required gates pass.
2. Verify actual production `config('mail.default')` is the intended Elite `sendmail` transport, with `info@kmjtechno.com` sender, Postfix direct-to-MX primary, Brevo fallback only and OpenDKIM. Do NOT change Cloudflare Email Routing/MX, signing material, other accounts or Google VPS.
3. Ensure queue worker and database queue are healthy. `BrandedCustomerNotification` implements `ShouldQueue` and schedules only after DB commit.
4. Verify source CI and staging MailMessage templates; run actual authorized owner-inbox **Laravel verification + password reset** tests with real signed-link action/expiry/security evidence. No production email is proven by template tests or `Notification::fake()`.
5. With owner approval, signed release via `docs/operations/FAST_RELEASE_GUIDE_ELITE.md`. The deploy process must show exact SHA approval, zero activation blockers, real pointer switch, migrations and health. No release bypass.
6. After live signed deployment and actual inbox acceptance, turn on the main flag privately on Elite using the reviewed runtime configuration path. Payment receipts require an additional independent approval.
7. Monitor mail job failures, bounce/expiry and actual recipient receipts; disabling these flags provides the rollback for *new* notices (already enqueued jobs need separate approved handling).

## Test command

```bash
cd apps/platform
php artisan test --filter=BrandedTransactionalSuiteTest
php artisan test --filter=BrandedAuthMailTest
```

Check exact PR HEAD GitHub CI and the full release gate. Tests use `Notification::fake()` for integration assertions; **no real emails or customer data** are sent.

## P0 independent delivery issue

See [Issue #391](https://github.com/kmjtechno/kmj-main-platform/issues/391). Source templates cannot solve outbound SMTP/Postfix delivery on their own. Latest owner read-only evidence: queue previously 0, not proof that old deferred mail delivered; root mail-health requires signed Supervisor rollout. Do not close P0 before authenticated inbox and verified signed-link acceptance.

## Customer-facing copy tone

Confidence without overclaiming. Concise first line, one primary action, human support path and precise lifecycle language. Keep receipts, renewals, alerts and account-security messages individually actionable; never auto-promote previews or assume entitlements.
