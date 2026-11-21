# KMJ-elite local health policy: owner-disabled offsite timer

## Verified incident — 21 November 2026

On KMJ-elite, the owner's intentionally disabled
`kmj-elite-offsite-backup.timer` caused the *independent local health
unit* to exit with code 3. The installed health shell script uses
`set -Eeuo pipefail`; its line 26 previously ran
`systemctl is-active --quiet kmj-elite-offsite-backup.timer` even though
the owner explicitly reserves Google VPS exclusively for CloudOS tests.

Owner applied a guarded, backed-up live script repair on 21 November at
12:20Z. The actual service journal returned
`KMJ_OFFSITE_TIMER=DISABLED_BY_OWNER; DR=NOT_VERIFIED` and
`KMJ_ELITE_HEALTH_PASS`; independent CodeBridge Supervisor receipt
verified `unitExit=0`, `unitInvocationPass=true` and marker true at
17:50 IST. Original backup: `/usr/local/sbin/kmj-elite-health-check.bak.20261121T122011Z`.

The owner-selected single-Elite routine deployment contract has **no Google
VPS staging/signing/release dependency**. Independent offsite recovery
remains **NOT VERIFIED**, not healthy. This incident was not proven caused
by remote IP/DNS/host-key drift; the root-owned installed code established
the stale offsite timer gate.

## Permanent source representation

`scripts/operations/elite_health_owner_disabled_offsite.py` is a small
source-controlled, **source-only** opt-in reconciliation utility.
It is not installed by a PR merge or GitHub Actions.

- `--inspect`: strict read-only identity/shape check and status
  `ALREADY_APPLIED`, `READY_FOR_OWNER_APPLY`, or `BLOCKED_...`.
- `--apply`: owner/root on host `KMJ-elite` **only**, after independently
  verifying that the main scheduler timer is active and the offsite timer
  is **inactive and disabled**. It never starts or enables a timer.
- It replaces only the exact historic offsite timer requirement with
  the owner-selected conditional: active timer is acceptable, or inactive
  **and explicitly disabled** is acceptable with `DR=NOT_VERIFIED`.
  Unexpected offsite timer states still FAIL.
- It refuses symlinks, multiple hardlinks, unsafe path ownership/mode,
  missing/reordered exact local DB backup/fresh encrypted archive
  checks, script drift, and source races; preserves script mode/owner;
  writes an exclusive timestamped backup before any replacement;
  checks Bash syntax before atomic replace.
- It never changes the PostgreSQL/Redis/Nginx/CodeBridge/SSL/database,
  local backup freshness (lines 25 and 28), owner safety/approval,
  recovery artifacts, production pointers, DNS or root timer state.
  It never manufactures backup, release, independent DR or rollback proof.

CI: `python3 scripts/test_elite_health_owner_disabled_offsite.py -v`.
Tests cover conditional policy, idempotency, preservation of backup checks,
untrusted script drift/duplicate/mixed/reordered lines and unexpected timers.

## Owner installation / evidence boundaries

For **future** reviewed rebuilds only, first review the exact PR/commit
and its completed exact-head CI, locally pin the script bytes via SHA-256
and compare with independently reviewed content. Do not use a mutable URL
or install unsigned unreviewed source. Inspection may be run before
applying. The owner must authorize the fixed source, and it is never
automatically activated by merge or by an agent.

After an owner-approved change, run
`bash -n /usr/local/sbin/kmj-elite-health-check`,
then `systemctl start kmj-elite-health-check.service` under the owner's
own change window and read back the **new invocation** from
`systemctl show` and `journalctl -u`.
Only `Result=success`, `ExecMainStatus=0` and the own-invocation
`KMJ_ELITE_HEALTH_PASS` together prove health-unit PASS. A manual
one-shot does **not** prove the next scheduled timer run, independent
disaster recovery, or successful production deployment. Preserve the
owner-disabled offsite timer state throughout.
