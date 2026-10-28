# KMJ continuous production delivery: guarded, zero-new-cost

**Canonical customer website:** https://kmjtechno.com. `staging.kmjtechno.com`
is exclusively a release-test origin. GitHub merge, `staging-approved`
promotion, an isolated build, or HTTP 200 are NOT equivalent to a live release.

## Goal and boundaries

When the owner has granted *exact-release* authorization after independent QA,
offsite recovery and rollback evidence, a root-owned systemd timer can call
the **existing fixed privileged production-release service** without repeated
ChatGPT terminal prompts. The pre-existing service is the only actor allowed
to switch the production release; it independently verifies its protected
manifest, backup SHA-256, target source identity, web health and rollback.
The new gate is an additional restriction, never a replacement.

This is a source-only proposal until exact-head CI, code review, authorized
installation and private-owner acceptance are complete. No production systemd
files are installed, no timer is enabled and no live release is changed by
merging this source.

## Admission chain (fail closed)

1. Main Platform code passes normal build, unit, database, owner-role,
   locked-desktop/mobile and browser QA CI; `staging-approved` is promoted.
2. An exact immutable `platform-<sha12>` production candidate exists,
   owned by its restricted account, with validated assets. The candidate is
   NOT the production current symlink.
3. The canonical staging origin serves **exact** `X-KMJ-Deploy-SHA`,
   no redirect to production, normal TLS, owner-authenticated Super Admin and
   Product Studio QA, approved locked visuals, live assets, and correct RBAC.
4. Independently verify the **same candidate's** encrypted offsite DB/storage
   recovery, reversible migration/storage continuity, and rollback. Neither
   an old archive nor a directory-exists check proves restore success.
5. The owner independently reviews the evidence and only then authorizes the
   exact SHA under both existing root-owned
   `/etc/kmj-codebridge/main-platform-production-release.json` and new
   `/etc/kmj-codebridge/main-platform-autopublish-<sha12>.json`.
   Both must be real, root-owned, non-symlink, single-link, mode 0600 (or
   more restrictive), and written by an approved **separate** owner procedure,
   never by the auto-publisher or an untrusted development checkout.
6. Timer's exact-source gate verifies the current production release matches
   the protected expected-old release, latest remote `staging-approved` SHA
   matches the exact authorized SHA, candidate Git HEAD matches, strict
   protected root-owned evidence agrees, every acceptance gate is boolean true.
   Missing/stale/contradictory fields or network failure => no deployment.
7. It calls only the existing **fixed**
   `kmj-main-platform-production-release.service`, with no arguments.
   That existing unit must also pass ALL of its own root approval and backup
   checks. Its no-exceptions rollback is preserved.
8. Read back the actual live release and HTTPS `/login` (200). Independently
   re-run production authenticated/browser checks; flag any mismatch and
   investigate rollback rather than claiming success.

The additional per-release admission JSON contract (example **only**, not
real evidence or permission to prefill booleans):
```json
{
  "schema": "kmj.autopublish.release-admission.v1",
  "approvedSha": "<independently-reviewed-exact-40-hex-SHA>",
  "expectedCurrentRelease": "platform-<verified-old-sha12>",
  "stagingSha": "<same-exact-40-hex-SHA>",
  "standingOwnerAuthorization": false,
  "ownerAuthenticatedQaPass": false,
  "stagingExactShaPass": false,
  "independentOffsiteRestorePass": false,
  "rollbackRehearsalPass": false,
  "migrationAndStorageContinuityPass": false,
  "publicOriginQaPass": false
}
```
The above placeholders deliberately cannot pass the gate. Never set any PASS
or authorization without independently preserved matching evidence, including
a fresh owner-qualified approval for each release. A generic "approved all"
statement does not validate a different future SHA. Don't allow any automated
job to create or overwrite these protected attestations.

## Unit templates (not yet installed)

- `scripts/operations/main_platform_autopublish_gate.py`:
  `--check` performs non-mutating admission; `--activate` conditionally
  triggers only the installed root-owned fixed release service. No custom
  shell/script paths, production symlink edits, DNS, database or secrets.
- `infra/server/systemd/kmj-main-platform-autopublish.service`:
  hardened one-shot gate referring to a separately installed trusted script
  at `/opt/kmj-main-platform-autopublish/main_platform_autopublish_gate.py`.
- `infra/server/systemd/kmj-main-platform-autopublish.timer`:
  check every ten minutes on the existing VPS (no cloud service or fees).

**One-time setup requires a reviewed, exact SHA-verified root installation.**
An operator must pin the source commit, copy it to a root-owned non-writable
directory, verify both script hash and service templates, inspect unit
sandbox and explicit user authorization, `systemd-analyze verify`, then enable
the timer. Never `curl | bash`, disable the existing release safety gate,
or start the timer before a safe end-to-end rehearsal on a disposable
environment. Do not use a network-fetched unsigned manifest as proof.

## Verified release state, 2026-10-28

`main` and `staging-approved` agreed at
`ad4cfa68291ec6a05e88f30ed0a93b2d15af40fe`; isolated staging and
production candidates both built and verified by the CodeBridge receipt.
This does **not** mean the staging origin is serving that SHA:
the live staging exact-SHA probe failed. Current customer production remains
`platform-8070dad72c55`, protected approval expects older
`platform-54142f844c0b`, and supervisor reports
`readyToActivate=false`. Fresh candidate-specific owner acceptance,
independent encrypted offsite restore and rollback approval are not yet
verified. Therefore **do not enable unattended publication** as of this
evidence. If any gate is absent, continue qualified development and evidence
work instead of forcing live.
