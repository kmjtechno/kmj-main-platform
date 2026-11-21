# KMJ Main Platform: Elite staging and production release runbook

Status: working procedure as actually used on 2026-11-21 (releases `489259d0`, `b9da1c75`, `97da757c`). It is a procedure, not evidence that any particular release is safe. Every release still needs its own exact-SHA evidence.

Target: KMJ-elite only (CodeBridge device `kmj-elite-main-platform`, project `kmj-main-platform`). No Google VPS, no P520, no paid resources.

## Who may do what

| Step | Claude / ChatGPT agent | Owner (root) |
|---|---|---|
| Pick the SHA, check CI, check migrations and script pins | yes | no |
| Build the release one-click command | yes | no |
| Run the command on Elite | no (needs root) | yes |
| Read production status, activate the approved SHA (Supervisor tools) | yes | no |
| Run database migrations | no | yes (separate root command) |
| Attest backup and rollback (`--attest-backup --attest-rollback`) | never | yes, this flag is the owner's own attestation |
| Browser checks on the live site | yes | no |

An agent never passes the attestation flags itself, never edits a protected approval manifest, never reuses an old approval, and never bypasses a blocker. If a gate says blocked, stop and report.

## 1. Choose the candidate

1. Use a commit that is already on `main`. Do not release a branch.
2. Read all check runs for that exact SHA. All must be completed and successful (skipped is fine). No pending, no failed.
   `gh api repos/kmjtechno/kmj-main-platform/commits/<SHA>/check-runs`
3. Read the freeze state in the CodeBridge mailbox (`coordination_list`). If another agent announced a freeze or an in-progress release, wait.
4. Post a mailbox note: candidate SHA, current live release, "main freeze until activation".
5. Check what changed since the live SHA:
   - `git diff --name-only <LIVE_SHA> <SHA>`
   - Any file under `database/migrations`? Then a separate owner migration step is needed (section 5). Releases never run migrations.
   - Any change under `scripts/operations`? Then the pinned hashes below must be re-verified and re-pinned in the command.

## 2. Pinned scripts

The release chain downloads each script at the candidate SHA and refuses to continue if the hash differs. Pins as of main `97da757c` through `57c2fc77` (unchanged):

| Script | SHA-256 |
|---|---|
| `scripts/operations/stage-fast-main-candidate-no-activation.sh` | `ebdb77fa56e8e48c32e21d7d1c53a28c56666dd0cc7c002d200706478e1e9a24` |
| `scripts/operations/main_platform_storage_switch.py` | `281893b277fb4dfabf174b7baaa49801f6b0a4c2dc83c2c711115f45225ea8ef` |
| `scripts/operations/materialize-main-platform-candidate-runtime.sh` | `fd29c4ebcf224c45786f8cedd0e0d42bbfd414d706678fe820e0ead4eea3984f` |
| `scripts/operations/prepare-main-platform-local-recovery-exact.sh` | `d3f977dbd68bd986e888c720c2bcc49e1c02e884878bfc4e4c0903f53bdf3212` |
| `owner_main_platform_production_approval.py` (kmj-codebridge commit `8cb6cce3`, `scripts/production`) | `e4c2b9d8f873f9bc7c7d9e78f248aa983b4c221a1d27a8fd520c16fb201b5ffe` |

Verify before handing the command over:

```
for f in stage-fast-main-candidate-no-activation.sh main_platform_storage_switch.py \
         materialize-main-platform-candidate-runtime.sh prepare-main-platform-local-recovery-exact.sh; do
  curl -fsSL https://raw.githubusercontent.com/kmjtechno/kmj-main-platform/<SHA>/scripts/operations/$f | sha256sum
done
```

If a hash differs because a script was legitimately changed, that change needs its own review. Do not just paste the new hash.

## 3. The owner one-click command (stage, storage, materialize, recovery, approval)

Set `SHA` to the candidate and `LIVE` to the current live release directory name (read it from `supervisor_main_platform_production_status`, field `currentRelease`; it looks like `platform-<12 hex>`).

```
bash -c 'set -Eeuo pipefail
SHA=<40 hex candidate>; LIVE=platform-<12 hex current live>; S12=${SHA:0:12}
MP=https://raw.githubusercontent.com/kmjtechno/kmj-main-platform/$SHA/scripts/operations
CB=https://raw.githubusercontent.com/kmjtechno/kmj-codebridge/8cb6cce343c8e8f9fe0b6517362c95d0b61bc7d1/scripts/production
D=$(mktemp -d); trap "rm -rf $D" EXIT; cd $D
get(){ curl -fsSL "$1/$2" -o "$2"; echo "$3  $2" | sha256sum -c - >/dev/null || { echo "HASH_MISMATCH $2"; exit 2; }; }
get $MP stage-fast-main-candidate-no-activation.sh ebdb77fa56e8e48c32e21d7d1c53a28c56666dd0cc7c002d200706478e1e9a24
get $MP main_platform_storage_switch.py 281893b277fb4dfabf174b7baaa49801f6b0a4c2dc83c2c711115f45225ea8ef
get $MP materialize-main-platform-candidate-runtime.sh fd29c4ebcf224c45786f8cedd0e0d42bbfd414d706678fe820e0ead4eea3984f
get $MP prepare-main-platform-local-recovery-exact.sh d3f977dbd68bd986e888c720c2bcc49e1c02e884878bfc4e4c0903f53bdf3212
get $CB owner_main_platform_production_approval.py e4c2b9d8f873f9bc7c7d9e78f248aa983b4c221a1d27a8fd520c16fb201b5ffe
bash stage-fast-main-candidate-no-activation.sh $SHA
APP=/home/kmjprod/releases/platform-$S12/apps/platform; SH=/home/kmjprod/shared/storage
PID=$(python3 main_platform_storage_switch.py plan --app-dir $APP --shared $SH | python3 -c "import sys,json;print(json.load(sys.stdin)[\"plan_id\"])")
python3 main_platform_storage_switch.py switch --apply --plan-id $PID --app-dir $APP --shared $SH
/bin/bash -p materialize-main-platform-candidate-runtime.sh $SHA $LIVE
bash prepare-main-platform-local-recovery-exact.sh $SHA $LIVE
python3 owner_main_platform_production_approval.py --sha=$SHA --live=$LIVE --apply --attest-backup --attest-rollback
echo CHAIN_EXIT=0'
```

What each step does:

1. `stage-fast-main-candidate-no-activation.sh`: builds the exact SHA into `/home/kmjprod/releases/platform-<12 hex>` without activating it. Expect `KMJ_FAST_STAGE=PASS` and `KMJ_PRODUCTION=UNCHANGED`.
2. `main_platform_storage_switch.py plan` then `switch --apply --plan-id`: makes the candidate use the shared storage directory. Expect `STORAGE_MODE=VERIFIED_SHARED`.
3. `materialize-main-platform-candidate-runtime.sh`: carries the production `.env` into the candidate byte-identical and checks nginx denies the private env. Expect `RUNTIME_ENV=BYTE_IDENTICAL`, `PENDING_MIGRATIONS=<n>`, `LIVE_RELEASE=UNCHANGED`, `KMJ_MATERIALIZE=PASS`.
4. `prepare-main-platform-local-recovery-exact.sh`: takes a local production database dump bound to the exact SHA and restores it into a disposable PostgreSQL to verify it. Expect `LOCAL_BACKUP_INTEGRITY=PASS` and `LOCAL_DISPOSABLE_POSTGRES_RESTORE=PASS`. The output states plainly that offsite restore and a physical rollback drill are `NOT_VERIFIED`; keep saying so in reports.
5. `owner_main_platform_production_approval.py`: writes the protected approval for exactly this SHA and this predecessor. The attestation flags are the owner's statement that a backup exists and rollback is understood.

The owner replies "done" when the output ends with `CHAIN_EXIT=0`. Any other ending: read the last lines, do not retry blindly, and do not skip a failed step.

## 4. Activate (agent, through the Supervisor tools)

1. `supervisor_main_platform_production_status` for the device and project. Require `approvedSha == <SHA>`, `expectedCurrentRelease == <LIVE>`, `approvalReady == true`, `activationBlockers == []`, `readyToActivate == true`, nginx and php-fpm active.
2. If it is not ready, stop. Typical causes: approval still for an older SHA (the owner command did not finish), or the live release moved. Do not replay an old approval.
3. `supervisor_main_platform_production_activate` with `approvedSha`, `expectedCurrentRelease` and `confirmation: "ACTIVATE_APPROVED_PRODUCTION_RELEASE"`. It returns `accepted: true` only. Accepted is not deployed.
4. Wait about 45 seconds, then read status again. Expect `currentRelease == platform-<S12>`, `releaseUnit.result == success`, `execMainStatus == 0`. The blocker `PROTECTED_EXPECTED_CURRENT_RELEASE_MISMATCH` appearing afterwards is normal: the approval was for the previous live release.

## 5. Migrations (owner, separate root command)

Releases do not migrate. If section 1 found migrations, hand the owner one command:

```
runuser -u kmjprod -- php8.4 /home/kmjprod/current/apps/platform/artisan migrate --force
```

Run it only after the release is active. Order matters when the new code needs the tables: until migrated, affected routes may return 503 (this happened with `payment_webhook_events` on 2026-11-21 and resolved after migrating). Take the stated local backup first for any destructive migration, and never run a destructive migration without explicit owner approval.

## 6. Verify the live site

- Open the relevant pages in the owner's signed-in Chrome (Claude in Chrome) and look for the new behavior. Pages behind password confirmation will redirect; do not enter the owner's password. Report what could not be checked.
- Public pages return 200. Security headers are present on web, API and health responses.
- `kmj-elite-health-check` own-invocation result via the Supervisor health receipt, when available.
- Keep the claim narrow: "release X is live and page Y shows Z". Do not say "production ready" or "secure". `RELEASE_GATE.md` defines what is required for those words.

## 7. Report

Post one mailbox note (`coordination_post`, kind `result`, with the exact SHA as `evidenceSha`): new live release, previous live release, what was verified, what is still not proven (offsite restore, physical rollback drill, exact-SHA staging test), and that the main freeze is lifted.

## Rollback

- The previous release directory stays in `/home/kmjprod/releases`. The release controller rolls back automatically if its own post-cutover checks fail. A physical rollback drill has not been performed; do not claim one.
- Manual rollback is an owner-root action. Do not improvise it; open an issue or post to the mailbox with the symptoms and the previous release name.

## Hard stops

- Do not change branch protection, repository settings, secrets, DNS, billing or signing keys as part of a release.
- Do not enable live charging, change payment mode, or create licenses or entitlements from payment events.
- Do not use the Google VPS or P520 for Main Platform deployment.
- Do not merge a PR with a failing or pending check. Merge your own PRs head-pinned (`gh api -X PUT repos/<owner>/<repo>/pulls/<n>/merge -f sha=<head> -f merge_method=squash`) only where the repository instructions allow it.
- Never print or store secrets, tokens or private keys in chat, logs or this repository.

Related: `docs/operations/CONTINUOUS_PRODUCTION_DELIVERY_20261028.md`, `docs/EASY_RELEASE_CD958.md`, `docs/PAYMENT_WEBHOOKS.md`, `RELEASE_GATE.md`.
