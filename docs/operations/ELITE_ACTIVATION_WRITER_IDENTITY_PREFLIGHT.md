# KMJ-elite one-click activation writer identity — root read-only preflight

**Source only. This is not an installed service, root-approved operator grant,
deployment, or staging/restore proof.**

PR #965 has 17/17 successful exact-head GitHub checks, but a security reviewer
raised a real gap: Laravel queues an exact-SHA intent as the production PHP-FPM
Linux identity, while the fixed Elite root broker only accepts a private
request file and directory owned by `kmjprod`. If the actual production
PHP-FPM worker runs as `www-data`, `kmjstage` or any other UID, the broker
must refuse. **Changing ownership or broadening the broker's permission
policy is NOT an acceptable shortcut.** The root inbox remains fixed at
`/home/kmjprod/shared/storage/app/private/ops/production-activation-request.json`.

## Read-only source gate

`scripts/operations/elite_activation_writer_identity_doctor.py --inspect`
can be run ONLY by root on **KMJ-elite**, after the operator has reviewed and
SHA-256 pinned the source to an immutable approved commit. It uses one fixed
read-only `systemctl show` on `php8.4-fpm.service`, then bound checks
`/proc` for the actual root PHP-FPM master and all direct live workers.
Every detected worker must be the exact installed PHP-FPM executable with a
known PHP-FPM pool title, direct master-child relation and all four real/
effective/saved/filesystem UIDs equal to the current `kmjprod` UID.

Before printing any success, it checks that each fixed ancestor of the inbox
is a real, non-group/other-writable directory owned by root or `kmjprod`;
the final inbox directory must be `kmjprod`-owned, owner-writable and
owner-searchable. Nonempty POSIX access/default ACL xattrs are deliberately
rejected rather than silently assuming they are safe. An existing intent
is reported as **BLOCKED_EXISTING_REQUEST_REQUIRES_RECONCILIATION** without
reading or deleting the file. Symlinks, hardlinked pending requests, wrong
UIDs, unverified ACL, unknown FPM workers or changing master PID fail closed.

A successful categorical receipt:

`KMJ_ACTIVATION_WRITER_IDENTITY=READY_FOR_OWNER_REVIEW_NOT_INSTALLED`

means **only** that a bounded snapshot of the actual local PHP worker
processes and private inbox appeared mutually compatible at inspection time.
It is not proof of which exact nginx FastCGI listener will serve a future
request, no proof against runtime races, no permission to run an activation
request and no proof of independent rollback, staging origin, root source
signature or production release readiness.

**No secrets or private intent contents are returned.** The script does not
create the inbox, touch `.env`, chmod/chown, start systemd, invoke git,
connect to Google VPS, change timer state, issue a license or switch live.

## Required next review gates

1. Independently verify actual production nginx → FastCGI target/pool identity.
   A multi-pool PHP-FPM master is intentionally treated as ambiguous unless
   every direct worker uses the required identity.
2. Independently review **installed** root broker and installed fixed
   `main_platform_autopublish_gate.py` schema, SHA, owner, signature and
   permissions; repository CI cannot establish the installed files.
3. Confirm the exact owner-protected approved SHA and current LIVE
   predecessor CAS. Today's observed predecessor drift is BLOCKED and must
   NOT be silently rewritten.
4. Verify Elite-only staging SHA, owner-authenticated QA, independent local
   PostgreSQL+uploads disposable restore and rollback evidence.
5. Obtain required independent GitHub security review from an eligible
   collaborator, then owner-approved signed immutable installation.
6. Re-run read-only identity preflight and all independent Supervisor checks
   before each owner-authorized change. Activation request remains
   conditional and no start is proof of a successful release.

CI verifies negative UID, chmod/ACL, unexpected worker, wrong host,
fake process status, existing intent and CLI mutation attempts without root.
