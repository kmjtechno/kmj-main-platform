# KMJ-elite release prepare broker — reviewed source only

**No installation, no production deployment, no new trusted grants by PR merge.**

Goal: remove the owner's root terminal from "stage and approve a release". The owner clicks once in the
private Ops page (later PRs: route and UI); a root broker then runs the owner's own pinned release helper in
its bounded `--prepare-only` mode, and later runs `--post-activation` (migrate) once the candidate is live.

## What the broker does

1. Reads one short-lived intent (`release-prepare-request.json`, schema `kmj.elite.release-prepare-intent.v1`):
   exact 40-hex SHA, actor id, 120 s window, plus two explicit owner attestations
   (`owner_backup_rollback_attested`, `migrate_after_activation_accepted`).
2. Refuses unless the SHA is exactly the current GitHub `main` head and every check run of that exact head is
   completed and successful (at least 6 runs, count must match, `skipped` is not success).
3. Fetches the helper for that SHA and refuses unless its sha256 equals the digest pinned in the broker.
4. Claims the intent once (no replay), always consumes it afterwards, runs
   `owner-release-main-platform.sh --prepare-only <sha>` with a cleared environment and a 60 minute bound,
   and records `prepared.json` only if the helper printed its exact success marker and no `BLOCKED` text.
5. On every timer tick, if a prepared candidate is live (`/home/kmjprod/current` resolves to
   `platform-<sha12>`), runs `owner-release-main-platform.sh --post-activation <sha>` once.
6. Writes an owner-readable status (`release-prepare-status.json`) for the Ops page. A status is a report, not a
   release proof.

## What it never does

It never activates production (activation stays the separate guarded activation broker / Supervisor step),
never starts the production release unit, never takes a SHA other than main head, never takes a command, path
or flag from the web request, and never runs the helper if its digest differs from the pin.

## Honest trust boundary

The intent file is written by the web application, so a compromised web app could ask root to prepare the
current `main` head, which is a commit that already merged and passed exact-head CI. It cannot choose another
SHA, cannot choose helper arguments, cannot skip the owner approval written by the pinned helper's own
attestation flags (the intent's attestations stand in for the flags the owner passes today), and still needs the
separate activation step. The owner's passkey step-up happens in the web request before the intent is written
(later PR). Because the helper is the owner's root script, the unit is intentionally not `ProtectSystem=strict`.

## Install (NOT DONE)

Later PR: pinned installer update. Until the owner runs it, nothing here exists on Elite.
Tests: `python3 scripts/test_elite_release_prepare_broker.py -v` (offline; no helper, network or root).
