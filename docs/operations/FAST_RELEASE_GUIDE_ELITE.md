# Fast release guide: KMJ Main Platform on Elite (for Claude, ChatGPT and the owner)

Status: operating guide, updated 2026-11-23. It describes the release path used for `platform-f8928845aae8` and
`platform-5ebee1e786fd`. It is not a proof that any given commit is release ready: that still needs
`RELEASE_GATE.md` and exact-head evidence. The longer reference is `ELITE_RELEASE_RUNBOOK_20261121.md`.

## Who does what

| Step | Who | Why |
| --- | --- | --- |
| Merge a PR to `main` | the agent that opened it, only after every check of the exact head is green | repo merge protocol |
| Run the release script as root on Elite | the owner (one command) | needs root and contains the owner's backup/rollback attestation |
| Activate the approved release | Claude or ChatGPT through the CodeBridge Supervisor tool, only after the owner's script has printed `APPROVAL_DONE_WAITING_FOR_ACTIVATION` | the owner approval is the release approval |
| Verify the result | the activating agent | "accepted" is not "deployed" |

An agent never runs the root script, never supplies the attestation flags itself and never activates a SHA the
owner has not approved.

## Rules

1. One release at a time. The stage step holds `/run/lock/kmj-main-platform-production-release.lock`;
   `KMJ_FAST_STAGE=BLOCKED_PRODUCTION_RELEASE_BUSY` means another run is active. Do not start a second one.
2. Freeze `main` while a release is in flight: `main` must equal the candidate SHA. Do not merge anything until
   activation and migrate finished.
3. The candidate is always a full 40-hex `main` SHA whose exact head passed CI.
4. Never paste long multi-block scripts into PuTTY (connections drop and copies run twice). Use the one-liner
   below, preferably inside `tmux`.
5. Do not put tokens, keys or customer data into chat, PR text or logs.

## Split modes (2026-11-23)

The helper also has two bounded modes so nobody has to keep one terminal open for the activation wait:

- `bash orm.sh --prepare-only <SHA>`: stage, storage switch, materialize, recovery and the owner approval, then stop
  with `APPROVAL_DONE_PREPARE_ONLY_ACTIVATE_THEN_RUN_POST_ACTIVATION`. It never waits for or triggers activation.
- `bash orm.sh --post-activation <SHA>`: runs only `migrate --force` on the live app and refuses with
  `BLOCKED_CANDIDATE_NOT_LIVE` unless `current` is exactly `platform-<sha12>`. It downloads, stages and approves nothing.

The no-flag form is unchanged (full chain with the 15 minute wait). **The old 71f77d40 helper pin is obsolete**;
current 2026-11-23 helper SHA256 is `325b24d32ebcf01b42994276a7beb550ed72c69cb044f8ffab03db6f1e218cec`.
The release helper has been hashed against the exact `main` source and matches the broker pin.
Always verify the helper digest again at the exact final merged candidate SHA.

## Release (owner, root, one command)

Replace `<SHA>` with the 40-hex `main` commit. The helper is pinned by sha256 and downloads four hardened helpers
plus the approval tool, each pinned by sha256 (a mismatch aborts before anything runs).

```bash
SHA=<SHA>
curl -fsSL "https://raw.githubusercontent.com/kmjtechno/kmj-main-platform/$SHA/scripts/operations/owner-release-main-platform.sh" -o /root/orm.sh \
 && echo "325b24d32ebcf01b42994276a7beb550ed72c69cb044f8ffab03db6f1e218cec  /root/orm.sh" | sha256sum -c - \
 && bash /root/orm.sh "$SHA"
```

If the helper file changes in a later commit, its pinned sha256 changes too. Compute it from the reviewed merge
commit (`git show <commit>:scripts/operations/owner-release-main-platform.sh | sha256sum`) and do not take it from
an unreviewed source.

**Short terminal mode (recommended when owner prefers not to leave the terminal open):** after verifying the
exact final SHA and digest, run `bash /root/orm.sh --prepare-only "$SHA"`; it produces
`APPROVAL_DONE_PREPARE_ONLY_ACTIVATE_THEN_RUN_POST_ACTIVATION` without activating or migrating.
Only after the trusted Supervisor independently confirms `readyToActivate=true` with the same SHA and predecessor
may the agent activate. After a fresh live pointer verification, the owner runs
`bash /root/orm.sh --post-activation "$SHA"` for pending migrations. Never interpret preparation as activation.
If main has changed or a release lock is busy, stop and re-evaluate rather than substituting a different SHA.

The script runs: stage, storage switch, materialize, local recovery, owner approval, then waits up to 15 minutes
for activation, and after activation runs `artisan migrate --force` as `kmjprod`. It prints
`APPROVAL_DONE_WAITING_FOR_ACTIVATION` when the approval is ready, and `CHAIN_EXIT=0` at the end.

## Activation (Claude or ChatGPT, via CodeBridge)

Device `kmj-elite-main-platform`, project `kmj-main-platform`.

1. `supervisor_main_platform_production_status` must show `approvalReady: true`, `approvedSha` equal to the
   candidate, `activationBlockers: []` and `readyToActivate: true`. Note `currentRelease`.
2. Call `supervisor_main_platform_production_activate` with:
   - `approvedSha`: the candidate SHA
   - `expectedCurrentRelease`: the `currentRelease` from step 1
   - `confirmation`: `ACTIVATE_APPROVED_PRODUCTION_RELEASE`
3. Wait about 45 seconds, then read `supervisor_main_platform_production_status` again. Success looks like:
   `currentRelease` is `platform-<first 12 of the SHA>`, the release unit `result: success` with exit 0, nginx and
   php-fpm active. `PROTECTED_EXPECTED_CURRENT_RELEASE_MISMATCH` in `activationBlockers` after activation is normal.
4. Tell the owner to confirm the script ended with `CHAIN_EXIT=0` (migrations ran). If it printed
   `NOT_ACTIVATED_YET_RERUN_ONLY_THE_MIGRATE_LINE_LATER`, activation did not happen: do not run migrate by hand
   against the old release.
5. Open the live site as the owner and check the changed feature. Report: SHA, release name, gate or CI evidence,
   what was and was not verified.

If the activation call is refused by the tool, stop and ask the owner. Do not retry with different values.

## Pinned helper hashes (unchanged across the last releases)

| Helper | sha256 |
| --- | --- |
| stage-fast-main-candidate-no-activation.sh | `ebdb77fa56e8e48c32e21d7d1c53a28c56666dd0cc7c002d200706478e1e9a24` |
| main_platform_storage_switch.py | `281893b277fb4dfabf174b7baaa49801f6b0a4c2dc83c2c711115f45225ea8ef` |
| materialize-main-platform-candidate-runtime.sh | `fd29c4ebcf224c45786f8cedd0e0d42bbfd414d706678fe820e0ead4eea3984f` |
| prepare-main-platform-local-recovery-exact.sh | `d3f977dbd68bd986e888c720c2bcc49e1c02e884878bfc4e4c0903f53bdf3212` |
| owner_main_platform_production_approval.py (kmj-codebridge @51ef2734) | `45b28a2d912c5e5b748ee4ec7c9df76e4b28e0ef32a23cc831169fe315136200` |

A change to any helper is a security-relevant change: it needs owner review and new pins in the same PR.

## What makes a release slow, and what is already faster

- The helper replaces copy/pasting a multi-block script with one pinned command.
- `composer install` during staging can take minutes; a hung composer holds the release lock. Wait before
  killing it. If the owner must stop a run, stop the process (`kill -TERM`), confirm the lock is free, then rerun.
- Not yet done: skipping composer when `composer.lock` is unchanged. It needs a reviewed change to the pinned stage
  helper and new pins everywhere.
- Not enabled: the activation broker (`ELITE_ONECLICK_ACTIVATION_BROKER.md`). Installing it is an owner security
  decision.

## Failure map

| Output | Meaning | Next step |
| --- | --- | --- |
| `KMJ_OWNER_RELEASE=BLOCKED_EXACT_SHA_REQUIRED` | not a 40-hex SHA | use the full SHA |
| `BLOCKED_WRONG_HOST` | not root on `KMJ-elite` | run on the Elite host as root |
| `BLOCKED_ALREADY_LIVE` | the SHA is already the live release | nothing to do |
| `HASH_MISMATCH_<file>` | a helper does not match its pin | stop, do not bypass, tell the owner |
| `KMJ_FAST_STAGE=BLOCKED_PRODUCTION_RELEASE_BUSY` | another release holds the lock | wait for or stop that run |
| `NOT_ACTIVATED_YET...` | nobody activated within 15 minutes | activate, then rerun the migrate line only |

## Never

No force push, no branch-protection or settings change, no merge of someone else's PR without the owner, no
production deploy because tests pass locally, no DNS, billing or signing-key change, and no claim of "released"
without reading the live pointer and the live site.
