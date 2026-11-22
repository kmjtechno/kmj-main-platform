# Elite-only operator release preflight — owner Ops integration

Status: source-only. This is an independently visible **read-only preflight** 
for issue #945; it does **not** complete Stage → Verify → Deploy.

## Safety architecture

- KMJ-elite remains the only routine staging/signing/deploy VPS. Google VPS
  is **only** for CloudOS tests. Independent disaster recovery is not verified
  by this feature.
- The existing root-owned fixed `main_platform_autopublish_gate.py` remains
  the sole authority for `READY_APPROVED_RELEASE` admission under owner-
  protected SHA/predecessor and Elite-local V2 backup/restore/QA gates.
- `scripts/operations/elite_release_readiness_receipt.py` is a fixed-path,
  root-only, **read-only** preflight publisher. It imports ONLY the already
  operator-reviewed installed gate at
  `/opt/kmj-main-platform-autopublish/main_platform_autopublish_gate.py`,
  rejects mutable/symlink/untrusted source identities, and reads the real
  approval, exact live pointer, GitHub promoted SHA and built candidate via
  the fixed gate's independent validation methods. For already-live, it also
  requires the actual canonical HTTPS exact-deploy-SHA check.
- Output is a small root-owned, single-link file at
  `/run/kmj-main-platform/release-readiness.json` in a root-owned directory,
  atomically refreshed only by the trusted root publisher. All false-proof
  dimensions stay `false`: `deploy_triggered`,
  `staging_origin_verified`, `scheduled_run_proven`,
  `independent_dr_verified`. A promoted GitHub SHA never proves the live
  staging **origin**.
- The PHP reader refuses untrusted file ownership/modes, symlinks, hardlinks,
  expired/future timestamps, invalid schema/host/source/shape, contradictory
  exact SHA or predecessor, fabricated deploy or DR flags. Missing receipt
  shows `unavailable`. No HTTP request or Laravel process executes root
  commands, builds releases, changes release approval, starts systemd or
  guesses production status.
- The owner Ops page shows Stage/Verify/Deploy readiness as blocked until
  each independently attested control is available. **Check release
  readiness** refreshes only existing Inertia telemetry; it is not Deploy.
  No success toast, fake 'staged', or deployment promise.

## Owner install helper (source only, nothing installed by merging)

`scripts/operations/install-elite-release-readiness-publisher-20261122.py` is a one-time, root-only,
SHA-pinned installer for the read-only publisher and its 30 second timer. It fetches only the exact
immutable commit it names, never overwrites, never starts the release unit and never writes an approval.
`--inspect` is read-only; `--install` writes the files without enabling the timer; `--install
--enable-timer` additionally enables only the publisher timer (the owner's explicit approval). Until it is
run, the Ops page correctly shows `NO_TRUSTED_ROOT_RECEIPT` and the activation request button stays
disabled. A fresh receipt is not a deploy, a staging-origin proof or a DR proof.

## Required further integration (not claimed here)

1. Sign/review the fixed root publisher, pin the exact bytes, then explicitly
   install an authorized read-only systemd timer on Elite. Do not run an
   unsigned script from a mutable branch or permit PHP to write the receipt.
2. Authorize the owner-only, fixed-capability CodeBridge broker to stage via
   the installed guarded unit, verify the actual staging HTTPS origin and
   owner-authenticated QA, attest independent same-SHA Elite PG+uploads
   disposable restore and rollback, then invoke the existing fixed privileged
   production unit ONLY after all protected current-LIVE SHA gates pass.
3. Implement genuinely idempotent release intent queue with exact-target
   SHA, previous-release CAS, short-lived owner confirmation, immutable audit,
   stuck job recovery, no-clobber, and readback from Supervisor before any UI
   displays success. Do not reuse the `delivery-control` low-risk action
   allowlist for release activation without a distinct reviewed broker.
4. Obtain explicit owner go and installer pin for each privileged deployment
   procedure. Keep intentionally disabled offsite timer OFF.

## Verification

- `python3 scripts/test_elite_release_readiness_receipt.py -v`
- `php artisan test --filter=EliteReleaseReadinessSnapshotTest`
- `php artisan test --filter=OperatorOpsConsoleTest`
- `npm run types` and normal exact-head GitHub CI.

This feature's `READY_APPROVED_RELEASE` means fixed gate preflight passed
when sampled, not that staging origin was independently witnessed or that a
deployment has been executed. A stale receipt is discarded. A normal
source PR merge never changes the live root owner script, Systemd, DNS,
backup timer, production pointer or approval.
