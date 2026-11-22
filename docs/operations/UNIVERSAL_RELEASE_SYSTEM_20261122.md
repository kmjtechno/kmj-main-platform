# KMJ Release Center: one one-click, faster release system for every KMJ project (design)

Status: design only, 2026-11-22, owner request ("one click, faster releasing for Main Platform and CodeBridge, and
if possible one system for all our projects"). Nothing here is implemented or approved by this document, and no
release, installation or trusted grant happens by merging it. It builds on what already exists and keeps the
owner's approval as the only release gate.

## What exists today (so we extend it, not replace it)

| Piece | State |
| --- | --- |
| Main Platform stage: exact SHA, CI, isolated build, smoke test | automatic (`stage-fast-main-candidate-no-activation.sh`, staging workflows) |
| Main Platform owner approval | root one-liner with backup and rollback attestation (`owner-release-main-platform.sh`) |
| Main Platform activation, health, rollback | guarded production release unit, started by an agent through the Supervisor tool |
| One-click activation from the owner Ops page | source merged (#965), broker installed on Elite 2026-11-22, **not yet proven end to end** |
| CodeBridge | signed stable manifest plus the owner's own `Get-FileHash` check, updater on each device |
| Other projects (CloudOS, OmniDesk, CineCore, Calibration Pro) | each has its own ad hoc flow |

## Goal

One **Release Center** page in the owner Ops area, one row per project, one primary button per row. The owner
does exactly one thing per release: review the candidate summary and click **Approve and release** (passkey and
step-up). Everything before and after is automatic.

## One contract, many adapters

Every project describes itself in a versioned `release.contract.json` in its own repo (schema checked in CI,
deny by default, no free-text commands):

- `project`, `kind` (`laravel-elite`, `node-service`, `windows-installer`, `cmake-qt`, `static-site`),
  `repository`, `default_branch`, `required_checks` (named CI jobs that must be green on the exact head).
- `stage` (named gate profile, never a shell string), `smoke` (named probe), `health` (named probe),
  `rollback` (named strategy), `data_risk` (`none` | `migrations` | `destructive`).
- `approval` (`owner-passkey`, always), `signing` (`none` | `owner-signed-manifest` | `code-signing-cert`).

An **adapter per kind** implements the three stages for it. Only `laravel-elite` and `node-service` are in scope for
the first release of this system; the others are added as their prerequisites exist.

## The three stages (as in the owner's plan)

1. **Stage and test (automatic).** Triggered when the exact `main` head has every required check green. Builds in
   isolation, runs the smoke probe, writes a root-owned readiness receipt. Failure posts to the coordination
   mailbox and stops. No human step.
2. **Approve (the only owner gate).** The Release Center shows exact SHA, predecessor, the changed-file summary, CI
   and smoke proof, migration risk and the rollback plan. A passkey click writes a signed, expiring, single-use
   intent. This replaces the root terminal command; the backup and rollback attestations are produced by the
   system from verified evidence (a fresh disposable restore) and displayed, not typed.
3. **Release (automatic).** The installed broker re-verifies the intent against the protected approval, starts the
   fixed release unit, runs canary and health, cuts over, and **rolls back by itself** if health fails. The result
   and live SHA are verified independently and posted to the mailbox.

## Speed

- Stage runs the moment `main` is green, so by the time the owner opens the Release Center the candidate is
  ready (today the whole stage waits for the root command).
- A single release lane per host, with `main` frozen only during cutover, replaces manual freeze coordination.
- Docs-only and frontend-only candidates can be marked `data_risk: none`, skipping migration and restore steps
  that cannot apply, while still requiring the click.

## Invariants (never negotiable)

1. Exact 40-hex SHA only, whose exact head passed every required check. No branch names, no arbitrary targets.
2. Every release needs the owner's own approval event. Auto-approval, scheduled approval and approval by an agent
   are out of scope. An owner-chosen "release at 02:00" is allowed only as a delay of an already approved SHA.
3. Contracts name gates and probes; they never carry commands, paths, environment or secrets.
4. Agents never hold the approval key, never edit another project's contract without that project's PR review.
5. A release that touches destructive migrations, billing, DNS, signing keys or the contract itself is shown as
   high risk and needs a second explicit confirmation.
6. "Accepted" is never "deployed": success needs the live SHA, health and an owner-visible check.

## Phases (each a small reviewed PR with exact-head CI)

1. Contract schema, validator and two contracts (`main-platform`, `kmj-codebridge`); read-only Release Center list.
2. Auto-stage on green `main` plus the readiness receipt for `laravel-elite` (replaces the root stage step).
3. Passkey approval writing the intent; system-produced attestations from a verified disposable restore.
4. Broker end-to-end proof on Elite with a real release, including a rehearsed rollback.
5. `node-service` adapter for CodeBridge (signed manifest flow kept; the owner signature stays the approval).
6. Windows and desktop kinds (CineCore, Calibration Pro) once a code-signing certificate and a Windows build host
   are provided; until then they stay manual and are labelled as such.

## Owner prerequisites

- Verify the broker install and the Ops preflight receipt on Elite (phase 4 needs a real approved release).
- A decision on who may click Approve and the step-up method.
- For Windows kinds: a code-signing certificate and a dedicated Windows build machine. Neither exists today.
- For CloudOS and OmniDesk: which host each releases to and whether it may share the Elite lane.
