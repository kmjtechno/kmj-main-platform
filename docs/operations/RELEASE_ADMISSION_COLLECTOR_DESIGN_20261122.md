# Release admission collector — design (no code, nothing installed)

Status: **design only**. It changes no gate, installs nothing, writes no approval and proves no release.
It exists so the one-click release has a real, reviewable path from "evidence" to the fixed gate's admission file
without anyone (human or agent) typing `true` into a flag.

## Why this is needed

`scripts/operations/main_platform_autopublish_gate.py` admits a release only when two root-protected files agree
on the exact SHA and the exact live predecessor:

1. the **approval** `/etc/kmj-codebridge/main-platform-production-release.json` (written 0600 by the owner helper), and
2. a per-release **admission** `/etc/kmj-codebridge/main-platform-autopublish-<sha12>.json` with schema
   `kmj.autopublish.release-admission.elite-local.v2`, where every acceptance flag must be literally `true`.

The owner-helper path used so far (root helper, then Supervisor activation) does not go through the admission file.
The Ops "Request approved activation" button and the root broker do. Until a trustworthy writer for the admission file
exists, that button can only ever end in `BLOCKED_ACCEPTANCE_SCHEMA`. That is correct and must stay correct.

## Rule that never changes

A flag is `true` only if a **fresh, exact-SHA receipt produced by a fixed root collector** says so. No UI, PHP
process, chat agent or CI result can set one. The owner's click only supplies `standingOwnerAuthorization`, and
only after every other flag already has a receipt.

## Flag to evidence mapping

| Admission flag | Receipt a collector must produce | What it must really check |
| --- | --- | --- |
| `stagingExactShaPass` | `staging-origin` | The staged HTTPS origin reports exactly the approved SHA (the existing exact-deploy-SHA check), not "GitHub main is that SHA". |
| `ownerAuthenticatedQaPass` | `authenticated-qa` | The fixed browser QA recipe passed against the staged origin with a real owner session (passkey step-up by the owner, never a stored credential). |
| `publicOriginQaPass` | `public-qa` | Anonymous browser QA (`/`, `/products`, `/login`, 3 viewports) passed on the staged origin. |
| `eliteBackupWitnessShaPass` | `backup-witness` | Fresh local dump + SHA witness bound to this candidate SHA. |
| `eliteDisposablePgUploadsRestorePass` | `disposable-restore` | A real isolated PostgreSQL + uploads restore of that backup, schema check and row-count parity, then destroyed. |
| `rollbackRehearsalPass` | `rollback-rehearsal` | Previous-release pointer switch and back on the staging pointer, health check after each, never on the live pointer. |
| `migrationAndStorageContinuityPass` | `migration-storage` | Pending migrations applied to the disposable restore only, storage link and public disk checks unchanged. |
| `standingOwnerAuthorization` | owner click | Owner passkey step-up in the Ops page, bound to the same SHA and predecessor. |

Each receipt: schema name, host, exact approved SHA, exact expected predecessor, captured_at, tool version and the
SHA-256 of the artifact it examined. Receipts older than a short window, with a different SHA/predecessor, a future
timestamp, a symlink or wrong owner/mode are ignored, exactly like the existing readiness receipt reader.

## Flow

1. **Collect (automatic, root, read-mostly).** A fixed root unit runs the collectors for the CURRENT approved SHA only
   and writes receipts under a root-owned run directory. Disposable restore and staging work never touch the live
   database, `.env`, live pointer or DNS.
2. **Show (read-only).** The Ops page and Release Center show each receipt as present / missing / stale with its
   age. A receipt is never shown as passing unless the root reader validated it.
3. **Approve (one owner click).** Passkey step-up creates an owner-intent. A fixed root broker re-verifies every
   receipt, the approval file and the predecessor, and only then writes the admission file with the flags derived
   from the receipts and `standingOwnerAuthorization: true`.
4. **Activate (existing).** The existing fixed gate and Supervisor/broker path activates. Post-activation health,
   automatic rollback to the previous pointer on a failed probe, and a post-release receipt.

## Invariants

- Admission file is written only by a fixed root broker, never by PHP, a chat agent or CI.
- Any missing, stale or mismatching receipt means no admission file. Fail closed.
- Collectors never run against production data or the live pointer, and never start the production release unit.
- No paid service, no external VPS dependency (Elite only), no secrets in receipts or logs.
- Do not loosen the gate, the approval modes (0600) or the predecessor check to make a release go through.

## Phases

1. Receipt schema + validator + root reader tests (source only).
2. Collectors, one per receipt, each with its own pinned owner installer and negative tests.
3. Owner-intent + broker admission writer (extends the existing activation broker, review required).
4. Ops UI: per-receipt status and the single approve click.
5. First real end-to-end release with every receipt real, recorded as evidence.

## Needs from the owner

- Confirm Elite is the only host for staging, restore and rollback rehearsal.
- Decide who may click Approve and which step-up is required.
- Approve each root installer separately (same pinned-installer pattern already used).

## Overlap

The Ops UI, intent queue and root broker belong to the issue #945 stream. This document names the contract between
that stream and the collectors; it does not edit those files.
