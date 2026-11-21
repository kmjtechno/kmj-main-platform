# KMJ-elite Postfix Queue Snapshot — Secret-Free Operator Tool

**Status:** Source candidate only. Not installed on KMJ-elite or exposed through CodeBridge.
**Date:** 2026-11-21; P0 mail issue [#391](https://github.com/kmjtechno/kmj-main-platform/issues/391).

## Why

Main Platform's canonical roadmap requires privacy, audit, observability and tested recovery. Owner-proven production uses Laravel `sendmail` → KMJ-elite Postfix **direct to MX primary** (`relayhost=`), OpenDKIM and Brevo **fallback only** (`smtp_fallback_relay=[smtp-relay.brevo.com]:587`). Inbound `info@kmjtechno.com` is separately routed by Cloudflare to owner Gmail.

The owner saw deferred Brevo `525` entries, later a **zero** queue after authorizing the Elite IP. **Queue empty is not proof of recipient delivery.** This tool makes that distinction explicit.

## Offline gate

```sh
python3 -m unittest -v scripts/operations/test_kmj_postfix_queue_snapshot_20261121.py
python3 -m py_compile scripts/operations/kmj_postfix_queue_snapshot_20261121.py
```

## Read-only usage (after exact SHA review / authorized host install)

Run as an operator with permitted queue inspection; it requires no environment variables, network, database or production source write.

```sh
set -o pipefail
sudo postqueue -j | python3 scripts/operations/kmj_postfix_queue_snapshot_20261121.py
```

It accepts only standard `postqueue -j` JSON lines on stdin; stdout contains fixed, aggregated keys for message/recipient counts, queue states, age buckets, prior recipient delay codes and `recipient_delivery_proven=false`. No sender, recipient, queue ID, message content or raw SMTP failure lines are emitted. Parser errors produce only `KMJ_MAIL_SNAPSHOT=INVALID_INPUT` and a nonzero exit, not partial or deceptive PASS data.

The 120h threshold is **only** the owner's measured `postconf -h maximal_queue_lifetime=5d` on 2026-11-21. If actual operator-configured lifetime changes, review the source constant before relying on its age warnings. Previous `525` entries can be stale after IP authorization until the next delivery attempt.

## Boundaries and future work

- Does not invoke `postqueue` itself, run `postqueue -f`, `postsuper`, edit Postfix, start OpenDKIM, send emails, change DNS, publish a release or access private log entries.
- Does not prove direct/fallback route selection or delivered inbox. Separately reconcile aggregate `sent/bounced/expired` events with authorized redacted mail logs and owner-controlled verification/reset inbox tests.
- Not an authenticated dashboard, timer, privileged Supervisor profile or automated alert. A follow-up hardened fixed-source, least-privilege CodeBridge Supervisor integration would require separate exact-head testing, review and owner installation approval.
- `QUEUE_MESSAGES=0` means **drained** only, not that all previous emails were sent successfully.

**Exit gate for P0:** exact candidate SHA, live Laravel signed verification + password-reset email to approved owner-controlled inbox, valid expiry and account binding, SPF/DKIM/DMARC alignment, and independent delivery/bounce evidence. Never mark P0 resolved solely from this utility.
