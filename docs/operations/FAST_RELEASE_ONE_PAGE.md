# FAST RELEASE: one page (Claude, ChatGPT and owner)

> **Start here.** This is the current, shortest release path for KMJ Main Platform on the Elite host.
> It was run end to end on 2026-11-24 for `platform-ad5e762b851c` and `platform-0f171fda626c`.
> Longer background and the older helper-script path: [`FAST_RELEASE_GUIDE_ELITE.md`](FAST_RELEASE_GUIDE_ELITE.md).
> This page is a procedure, not proof that a commit is release ready: that needs `RELEASE_GATE.md` evidence.

## Roles (not negotiable)

| Step | Who | Rule |
| --- | --- | --- |
| 1. Merge to `main` | the agent that opened the PR | only own, non-draft PR; every check of the **exact head** completed and successful; merge pinned to that head SHA |
| 2. `prepare` (root) | **owner only** | one command on the Elite host; the `--confirm` text is the owner's approval |
| 3. Activate | Claude or ChatGPT via CodeBridge | **only** after the owner writes exactly `activate karo <full 40-char sha>` in chat |
| 4. `post-activation` (root) | **owner only** | only if the release contains migrations |
| 5. Verify | the activating agent | status + public QA; "accepted" is not "deployed" |

An agent never runs the root commands, never invents the approval text and never activates a SHA the owner did not
name. Wording like "go ahead" or broad delegation is not the activation line.

## The 5 steps

**1. Merge and freeze.** `main` head must equal the candidate. Do not merge anything else until activation is done.
Confirm all checks on that exact head are green (agent):

```bash
gh api repos/kmjtechno/kmj-main-platform/commits/<SHA>/check-runs --jq '.check_runs[]|[.name,.status,.conclusion]|@tsv'
```

**2. Prepare (owner, root, one line).**

```bash
sudo kmj-fast-release --project main-platform --action prepare --sha <FULL_40_HEX_SHA> --confirm OWNER_APPROVES_PINNED_FAST_RELEASE
```

**3. Check readiness (agent).** CodeBridge device `kmj-elite-main-platform`, project `kmj-main-platform`:
`supervisor_main_platform_production_status` must show `approvedSha` = candidate, `activationBlockers: []`,
`readyToActivate: true`. Note `currentRelease`. If not, do **not** activate (see failure map).

**4. Activate (agent, only after the exact owner line).** `supervisor_main_platform_production_activate` with
`approvedSha` = candidate, `expectedCurrentRelease` = the `currentRelease` from step 3, and
`confirmation` = `ACTIVATE_APPROVED_PRODUCTION_RELEASE`. Wait about 45 seconds, then read status again:
`currentRelease` must be `platform-<first 12 of SHA>`, nginx and php-fpm active.
`PROTECTED_EXPECTED_CURRENT_RELEASE_MISMATCH` after a successful activation is normal.

**5. Post-activation and verify.** If the release has migrations the owner runs
`sudo kmj-fast-release --project main-platform --action post-activation --sha <SHA> --confirm OWNER_APPROVES_PINNED_FAST_RELEASE`.
Then the agent runs public QA: `run_project_command` command `browser_public_qa`, variant `start`, a unique
`requestKey`; read it with `browser_qa_receipt` (argument `job` = the returned job id). Report SHA, release name, QA
verdict and what was **not** verified. Post the result to the CodeBridge coordination mailbox.

## Failure map (seen in practice)

| Output | Meaning | What to do |
| --- | --- | --- |
| `FAST_RELEASE=BLOCKED:MAIN_HEAD_CHANGED_OR_SHA_NOT_MAIN` | someone merged after the candidate; the SHA is no longer `main` head | take the new head, re-check its CI, rerun prepare with the new SHA (the new head's changes ship too: read them first) |
| `FAST_RELEASE=BLOCKED:EXACT_HEAD_CI_NOT_ALL_GREEN` | a check on that exact head is pending or red | wait or fix; never override |
| status still shows an older `approvedSha` | prepare did not register | ask the owner for the last lines of the prepare output; do not activate |
| `readyToActivate: false` | blocker present | read `activationBlockers`; stop |
| activation tool refuses | protected precondition failed | stop and ask the owner; do not retry with other values |

## Never

No force-merge, no branch-protection or repository-setting change, no merging someone else's PR without the owner,
no activation without the exact line, no DNS/billing/signing-key/secret action, no claim of "released" or
"production ready" without reading the live release pointer and the live site and holding `RELEASE_GATE.md` evidence.
