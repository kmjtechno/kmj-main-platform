# Fresh-39 candidate: authenticated QA and isolated-rollback evidence requirements

Status: requirements only. Nothing here is evidence that candidate 39 (`39b88b3…`) is
releasable, and no old B2 / pre-39 proof may be reused (RELEASE_GATE.md: evidence must
belong to the exact release candidate). Source of gates: `RELEASE_GATE.md` and
`scripts/operations/main-platform-release-readiness-doctor.py`.

## What the readiness doctor already proves (read-only, root, exact SHA)
| Gate | Doctor key | Notes |
|---|---|---|
| Live pointer is a safe `releases/<id>` symlink | `CURRENT_RELEASE` | |
| Candidate dir exists, HEAD == target, clean tree, 4 artifacts non-empty | `CANDIDATE` | |
| Candidate `.env` present, mode 0600, not symlink | `CANDIDATE_RUNTIME_ENV` | existence only |
| nginx can read public asset, cannot read `.env` | `CANDIDATE_NGINX_ACCESS` | |
| `pre-deploy-<sha12>.json/.tar.gz` root-owned, schema, sha256 matches | `BACKUP_WITNESS` | proves archive integrity, not restorability |
| Approval file schema, SHA, expected current release, both flags true | `APPROVAL` | flags are owner assertions |
| Fixed activation unit + controller installed | `RELEASE_UNIT` | |

## What the doctor does NOT prove (must be supplied as separate evidence for the same SHA)
Each item: **artifact, produced by, pass condition**. Missing or from another SHA = NO DEPLOY.

1. **Authenticated Platform Owner QA on the candidate** (RELEASE_GATE "ADMIN QA")
   - Artifact: receipt listing candidate SHA, base URL (isolated port or staging host, never live), viewport list, and per-page result for: login, Product Manager create/edit/lifecycle/show-hide/ordering, `/services/kmj-codebridge`, `/operator/codebridge/owner-plan`.
   - Pass: HTTP 200, zero console/page errors, no horizontal overflow, no broken images, owner-plan shows read-only fleet summary with no pairing/disconnect/assign controls, canonical page shows Device Control Center and `#overview` / empty hash returns to Overview.
   - Must be a real authenticated owner session on the candidate runtime, not the synthetic Vite harness (`visual/entry.tsx` is explicitly synthetic and earns no release credit). If an owner login cannot be automated, status stays `PENDING_OWNER`, never PASS.
2. **Desktop + mobile (390px) public QA** on the candidate: `/` and `/products` 200, overflow/error/broken-image checks, full-page scroll for lazy assets.
3. **Build/diff/asset gates** bound to the candidate SHA: production frontend build exit 0, `git diff --check`, referenced assets load with non-zero dimensions (CI exact-head PASS for `39b88b3` counts only for source gates, not for the materialized runtime).
4. **Migration safety**: `pendingMigrations=0` was reported for materialization; additionally require that the candidate's migration set is a no-op or that each pending migration has a verified down path or a restore-based rollback. CI `migration-rollback` PASS on the exact head is required but is not a production-data proof.
5. **Fresh backup of current live DB + storage taken after candidate freeze** (the `pre-deploy-<sha12>` witness), with timestamp later than the candidate build receipt.
6. **Restore proof of that backup (disposable)**: restore into a throwaway PostgreSQL (`scripts/operations/verify-real-offsite-recovery.sh` pattern: no production DB connection, scratch on persistent disk, >=12 GiB free), then record row-count/schema checks and the storage manifest comparison (`verify-main-platform-storage-manifest.py`). Pass: restore exit 0, schema matches live, storage 0 regular / 0 symlink drift as in the materialization receipt.
7. **Offsite copy of the pre-deploy archive** with remote listing + checksum for the 39 object. Current Supervisor state is `recentBackupVerified=false restoreVerified=false` and the offsite unit last exited 255 (class AUTH); an old B2 restore does not cover 39.
8. **Isolated rollback rehearsal** (below) with receipt.
9. **Approval refresh**: protected approval must name target 39, `expectedCurrentRelease` equal to the live release at activation time, and `backupVerified`/`rollbackVerified` set true only after items 6-8 exist. The doctor currently reports it stale (expects `platform-8070dad72c55`).

## Isolated rollback rehearsal (never touches `/home/kmjprod/current`)
1. Copy nothing from live except a read-only reference to the previous release id; use a scratch root (e.g. `$HOME/kmj-rollback-scratch`, mode 0700, same device as `$HOME`).
2. Create `scratch/releases/<previous>` and `scratch/releases/platform-39b88b36d071` as bind-free copies or git worktrees at their exact SHAs; create `scratch/current -> releases/platform-39…`.
3. Serve each on a loopback-only port with the disposable restored DB from item 6 (never the live DB); run the health check the activation controller uses (static asset through nginx-equivalent plus `/` 200).
4. Flip `scratch/current` to the previous release atomically (`ln -sfn` + rename), re-run health: PASS means the pointer rollback path works. Flip forward again and confirm candidate health.
5. If any pending migration exists: run candidate migrate on the disposable DB, then restore the pre-deploy dump over it and confirm schema equals pre-migration schema (restore-based rollback). Pass criteria are schema + row counts, not "command exited 0".
6. Receipt fields: candidate SHA, previous release id, DB image checksum, health results (4 states), flip timestamps, scratch path removed after the run. `PRODUCTION_CHANGED=NO` must be asserted by also recording `readlink /home/kmjprod/current` before and after (identical).

## Fail-closed rules
- Any `FAIL`, `BLOCKED`, `PENDING_OWNER`, missing receipt, or SHA mismatch = NO DEPLOY.
- The assistant that produces evidence is not the approver: root approval creation, activation and live smoke remain owner/release-lane actions.
- No credential, token, key or raw log content in receipts.
