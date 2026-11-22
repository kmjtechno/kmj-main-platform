# KMJ-elite owner activation intent broker — reviewed source only

**No installation, no production deployment, no new trusted grants by PR merge.**

This adds the owner-click → independently guarded fixed-production-unit
execution boundary to issue #945. It is a production activation intent only
for a candidate which already has legitimate protected owner approval,
exact released predecessor, staging evidence, backup/restore and rollback.
It does not stage/build/test arbitrary candidates, attest DR, or manufacture
previously absent release approvals.

## One-VPS trust boundary

- KMJ-elite is the only routine Main Platform/CodeBridge staging, signing,
  release and execution host. Google VPS is reserved for CloudOS tests.
- The owner's password-confirmed and passkey-gated private
  /operator/ops page reads a fresh root-owned preflight receipt from
  PR #957. It shows Request approved activation only on
  READY_APPROVED_RELEASE, with exact approved SHA and predecessor.
- The route accepts only a 40-hex SHA and platform-12hex predecessor,
  plus explicit REQUEST_APPROVED_PRODUCTION_RELEASE confirmation.
  A successful web response means intent queued, NOT deployed.
- PHP audits actor and exact identity before an atomic create-only hardlink
  publishes a 90-second request. It never overwrites a pending request,
  including a dangling symlink, and cannot write protected manifests.
- A separately reviewed and pinned root-only broker may be installed
  on Elite. It reads only the fixed inbox, expects the kmjprod inode owner,
  safe directory permissions, mode 0640 single-link regular file, exact
  v1 schema, canonical v4 UUID, actor ID and bounded expiration. Rejects
  unknown, forged, repeated, expired, future and mismatched intents.
- Root independently rechecks the trusted fixed installed autopublish
  admission: the root-protected owner approval, staging-approved Git SHA,
  candidate Git identity, current LIVE predecessor, local restore, QA
  and rollback evidence. Only exact READY_APPROVED_RELEASE is admitted.
- Root checks the existing fixed production unit is loaded and inactive.
  It atomically records a root-only unique no-replay claim BEFORE asking
  systemctl to start ONLY kmj-main-platform-production-release.service.
  If systemd fails, the claim remains, demanding owner investigation;
  no blind retry or request deletion. A repeated claimed request returns
  ALREADY_REQUESTED_NOT_LIVE_PROOF, never a new deployment.
- A systemd start accepted is NOT proof of production activation.
  PASS requires independent Supervisor actual live currentRelease,
  fixed release unit result, HTTPS, database/queue/health verification
  and owner-authenticated QA.

## Required owner-host installation (NOT DONE)

1. Review and merge only full exact-head CI-green source/owner code;
   confirm no concurrent production release freeze.
2. Independently SHA-256-pin broker, already installed root preflight
   gate and unit templates. Do not run arbitrary mutable downloads.
3. Verify the real PHP inbox resolves to
   /home/kmjprod/shared/storage/app/private/ops/production-activation-request.json,
   with a real kmjprod-owned non-group-writable final parent, and the web
   process can create a 0640 file. No symlink/UID mismatch may be tolerated.
4. Install reviewed pinned broker as root at
   /opt/kmj-main-platform-activation/elite_owner_activation_broker.py
   plus systemd unit templates from
   infra/server/systemd/kmj-elite-owner-activation-broker.*.
   Verify exact SHA and owner/root identity; StateDirectoryMode=0700
   protects /var/lib/kmj-main-platform/activation-broker.
5. Explicit owner approval is required to enable the new timer.
   The PR does not call systemctl enable/start/restart, modify a
   protected approval, switch LIVE or reenable the disabled offsite timer.
6. For any actual activation first verify same candidate's staging origin,
   owner QA, real local PG+uploads disposable restore and rollback, exact
   head CI and owner protected approval. Broker --inspect never starts a
   service. No --execute test against an approved LIVE candidate.
7. After activation, independently verify the actual LIVE SHA via
   Supervisor and public/authenticated checks. Old request cleanup is
   a separate guarded reviewed owner procedure; never delete a pending
   or consumed intent silently.

## Owner install helper (source only, 2026-11-22)

`scripts/operations/install-elite-activation-broker-20261122.py` automates steps 2-5 above for the owner.
It fetches only the exact reviewed commit `2cd5f602fe06` (PR #965), writes the broker and the two unit
templates with a no-overwrite hardlink install, refuses to run unless the autopublish gate and the intent
inbox parent already exist, and verifies the units. `--inspect` is read-only. `--install` does **not** enable
the timer; `--install --enable-timer` is the owner's explicit approval to enable only the broker timer. It never
starts the production release unit, writes an approval or switches LIVE. Offline tests run in
`.github/workflows/elite-activation-broker-installer-qa.yml`. The status above stays **NOT DONE** until the owner
has run it and a real approved-release activation has been verified.

## Tests / truth boundaries

- python3 scripts/test_elite_owner_activation_broker.py -v
- php artisan test --filter=EliteActivationIntentTest
- normal Laravel, TypeScript, Foundation, PostgreSQL18 and browser QA
- dedicated source-only CI does NOT execute the broker or write LIVE

This is one-click execution only for a fully *pre-approved* release.
A trusted one-click Stage/Verify orchestration, owner installation and
future SHA-specific approvals remain separate pending work.
