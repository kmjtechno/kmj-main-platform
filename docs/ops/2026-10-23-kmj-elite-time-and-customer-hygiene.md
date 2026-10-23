# KMJ-elite time and unverified-customer hygiene — 2026-10-23

## Verified clock evidence
- Server timezone: Asia/Kolkata (IST, +05:30); NTP=yes; NTPSynchronized=yes.
- Server time observed: 2026-10-23 17:15:59 IST = 2026-10-23T11:45:59Z.
- Systemd timers observed for platform scheduler, server health, daily and offsite backups.
- Windows PC timezone: India Standard Time; Windows Time service was stopped (w32tm 0x80070426). The PC's NTP synchronization is NOT verified.

## Safe time standard
- Persist database timestamps, licensing/token/payment expiration and API instants in UTC.
- Render India-facing human dates in Asia/Kolkata; show explicit IST and +05:30.
- Preferred API string: 2026-10-23T17:15:59+05:30 or equivalent Z/UTC.
- Preferred user display: 23-10-2026 17:15:59 IST.
- Keep Laravel config/app.php timezone UTC for consistent token/payment/session deadlines. Do NOT backfill/reinterpret existing UTC timestamps.
- Audit next fire times of cron/systemd timers following timezone changes.

## Production unverified-account audit
After this PR is merged, tested, and safely deployed, use:
    php artisan kmj:users:audit-unverified --days=30 --json
This command only returns counts, never customer PII or identifiers. It does not update DB records or perform deletions. It always reports safe_to_delete_users=false and database_backup_verified=false.

## Mandatory guards before a future cleanup
- Independently verify restorable encrypted PostgreSQL backup; do not infer success from backup timer.
- Exclude platform owners, staff, active login/passkey/OAuth users, anyone with activation/licensing/payment/audit obligations.
- Reconcile legacy kslp_licenses.customer_id string linkage and any organization membership first.
- Verify schema foreign keys, outbox, sessions, payment events, regulatory and fiscal retention before any write.
- Use explicit dry-run candidate list and transaction-safe quarantine. Never blanket truncate or cascade delete.
- Do not bypass guarded Main Platform release pointer mismatch (readyToActivate=false).

## Evidence limitation
No production customer table was queried, modified, or cleaned during authoring. All unverified-user counts remain unknown until a safe operator audit is performed.
