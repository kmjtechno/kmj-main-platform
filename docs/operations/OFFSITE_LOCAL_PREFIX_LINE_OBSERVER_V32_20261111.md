# KMJ-elite offsite v32 — numeric-only local-prefix failure diagnosis

**Status (2026-11-11): source-only, unmerged, not installed.** This is a protected
engineering candidate, not evidence that automatic backups or independent
restores work.

## Why

The original `kmj-elite-offsite-backup.service` failed with SSH exit 255.
The v31 guarded SFTP repair passed SSH authentication and exact host-key
pinning but rolled back after local archive creation failed with
`LOCAL_BACKUP_PREFIX_FAILED` (exit 3). The v31 implementation explicitly
discarded local stdout/stderr and so could not identify the failing
prefix line. The previous successful rescue-transfer copied an **existing**
850,324-byte age ciphertext to the Google VPS with remote SHA-256 read-back
PASS; this was not an automatic service PASS or a restore test.

## v32 change

* Preserves exact SHA-pinned 31-line legacy source classification and executes
  only local lines 1–28. Legacy SSH assignment (line 29), rsync (line 30) and
  post-transfer command (line 31) are never executed.
* Places an ERR trap before the local prefix, which writes only its numeric
  Bash line number to an **anonymous inherited file descriptor**. Captured
  local stdout/stderr stay `/dev/null`, without tracing commands, secrets,
  environment, database contents or raw journal data.
* Maps this injected line to original lines 1–28. Accepts **exactly one
  canonical complete numeric marker**, rejecting duplicates, truncation,
  prefix/suffix junk, and out-of-range values. Emits only
  `LOCAL_PREFIX_ERR_TRAP_LINE_CANDIDATE=LINE_XX` or `UNKNOWN`; the
  marker is advisory, not cryptographic proof, and some shell failures such
  as explicit `exit` cannot be mapped.
* Uses distinct v32-only systemd repair executable/drop-in names so v31 is
  not overwritten. No service file is installed by creating this branch.
* Keeps strict Google SFTP host-key and client-key fingerprints, archive
  ciphertext validation, remote exclusive hard-link publication, remote
  SHA-256 read-back, unit attestation and attempted rollback.

## Zero-cost validation

Source and tests were copied SHA-bound from the authorized KMJ-elite
CodeBridge project to this feature branch and then byte-for-byte compared.
The anonymous-fd ERR-trap algorithm passed seven **isolated synthetic
non-root Bash scenarios** (success, failing lines 3/9/21/28,
explicit exit, output suppression and missing stdin). These are algorithm
tests, **not** a full root-service integration test. The ten included Python regression tests, including a strict canonical
single-line marker anti-spoofing case, still require the exact branch test
command to run before protected installation. The observer logic alone
passed eight non-root isolated local regression scenarios on 12 Nov 2026;
this is not an attested full-module or KMJ-elite service run.

No paid hosted CI, root command, systemd reload/restart, SSH transfer, DB
restore, Nginx change or production release action was performed by this PR
branch.

## Deployment gate

Do not install until the exact v32 SHA-256 is independently pinned, Python
syntax and nine offline tests pass, and a separately reviewed root-only
dry-run/rollback plan approves the one-shot service scope. If the v32 local
prefix still fails, collect only its categorical line marker and
invocation-specific exit status. **Never** disable `set -e`, SSH host-key
validation, age encryption or source SHA checks to chase green.

Once local failure is repaired, require a new autonomous encrypted archive,
remote SFTP SHA-256 read-back, **independent Google decrypt, disposable
PostgreSQL restore and storage parity** before declaring automated backup
production-ready. Production release pointer approval remains a separate gate.

## CodeBridge read-only observation (12 Nov, source-only)

The matching CodeBridge integration is developed separately on
[`feat/offsite-v32-line-supervisor-20261112`](https://github.com/kmjtechno/kmj-codebridge/tree/feat/offsite-v32-line-supervisor-20261112),
head `578a0cc3e2733f281cdaed54d8cf2e781cbc06d1`.
After an owner-approved signed agent/Supervisor rollout, the already-authorized
`main_platform_offsite_status` profile can report only the validated
`backupPrefixFailureLine=LINE_01..LINE_28|UNKNOWN`. It binds the journal to
the exact systemd invocation and requires exit 3; malformed or duplicate
markers cannot promote an error line. Raw journal and host secrets are never
returned, and no additional shell/root capability is added.

**Do not misread the source branch as installed:** as of 12 Nov 08:13 IST,
the existing KMJ-elite offsite service still reports exit 3 and the new
telemetry is not deployed. The signed updater remains disabled. Full
regression and approval gates must pass before either component goes live.
