# KMJ Main Platform — private GitHub Actions blocked: safe development QA

**Incident:** As of 17 October 2026, private-repository GitHub Actions jobs
in multiple workflows are failing **before test steps execute**. This is
tracked by [issue #437](https://github.com/kmjtechno/kmj-main-platform/issues/437).
An empty job log or instant failed run is **not** evidence that project tests
ran or passed. It is also not authorization to waive release requirements.

## What still works (baseline evidence only)

The already-connected `kmj-elite-main-platform` CodeBridge device can run
administrator-approved `fast`, `platform`, and `full` quality gates on
its *existing main checkout*. All three returned exit 0 on 17 October 2026:
`06c69810-47ab-4e42-8cfe-ec20ac9755fc`,
`b4fb47fc-ac40-4e23-b134-aa0001493adc`, and
`0a4b0b8b-9d73-4ff9-b3f6-6afa4848af1a`.
These are **not** checks for PR #442, #443, #444 or #445.

Another older approved CodeBridge command profile
`main_platform_ui_ci:build` still points to pinned worktree
`eb676253...` and fails `vp: not found` (exit 127). Do not fix it by
changing production dependencies or the current dirty/untracked checkout.
That command profile requires separate least-privilege runtime maintenance.

## Safe zero-extra-spend candidate verification

For a checked-out private repository with preinstalled, compatible
`apps/platform/vendor` and `apps/platform/node_modules`, an authorized
*unprivileged* operator can run:

```sh
cd /srv/kmj-codebridge-projects/kmj-main-platform
bash scripts/ci/verify-live-pr-head.sh 445 211d4ad9523e25a88b16204dda06874f15202f47 admin
```

Use a candidate's **current** PR number and latest 40-hex HEAD, not a stale
example SHA. Profiles: `frontend` uses the existing isolated dashboard/UI
check; `admin` uses existing isolated Super Admin checks; `postgres`
uses the existing isolated PostgreSQL staging suite with a fresh local
Unix-socket-only database cluster, never production PostgreSQL.

This guarded dispatcher verifies:
- exact approved GitHub origin and remotely advertised `refs/pull/N/head`;
- caller SHA equals **current** remote PR HEAD (otherwise refuse);
- pristine **tracked** source checkout (pre-existing **untracked** QA evidence
  is permitted and never touched);
- candidate object available; only the requested PR object's Git pack may be
  safely fetched if absent (no branch reset or checkout);
- candidate `composer.lock` and `package-lock.json` match preinstalled
  baseline dependencies. If not, refuse rather than silently using stale
  vendor/npm files;
- fixed, tracked, reviewed verifier scripts only; a scratch HOME and TMPDIR
  plus `env -i` prevent candidate PHP/Node processes inheriting production
  tokens, SSH agent, database credentials or GitHub tokens from the caller;
- all application test/build outputs remain in disposable worktrees, while
  production `.env`, PostgreSQL, Nginx, queues, DNS, payments and licensing
  remain untouched.

The script uses the existing specialized QA scripts and does **not**
install paid services, purchase Actions minutes, change GitHub branch
protection or change the repository to public. It cannot assert that
browser UI, owner authentication, payment gateways or real PostgreSQL
replication are healthy unless the chosen verifier explicitly tests them.

A successful local run must be labeled **LOCAL EXACT SHA PASS**, **not**
GitHub Actions PASS. Release still follows `RELEASE_GATE.md` and requires
the actual protected repository checks, screenshots/owner acceptance where
applicable, backup and tested rollback.

## Remaining external blockers (not repaired by a source PR)

1. **GitHub Actions runner/budget:** Owner or org billing admin must check
   the private-repository Actions execution/usage banner, spending limits,
   GitHub-hosted runner eligibility and organization Actions policies.
   Never buy capacity or add an unapproved runner under the ₹0 policy.
2. **CodeBridge GitHub bridge:** the live gateway returns
   `GITHUB_REPOSITORY_DENIED` for `kmjtechno/kmj-main-platform`.
   `src/github.js` enforces the exact `github.repositories` allowlist.
   Gateway operator must add **only this exact private repository** after
   verifying server-held GitHub App permission. Do not widen scopes or
   expose credentials; restore verified SHA and tool catalog with rollback.
3. **Autopilot lease mismatch:** published connected ChatGPT
   `autopilot_complete`, `autopilot_wait`, and `autopilot_checkpoint`
   tool schemas lack the server-required `leaseToken` property. See
   [CodeBridge issue #369](https://github.com/kmjtechno/kmj-codebridge/issues/369).
   Publish/recapture the proper tool schema; **never bypass lease fencing**.
   A claimed task is not completed merely because it was started.
4. **Unattended worker:** 21+ existing development tasks remain queued. An
   online MCP agent is not evidence of a running autonomous worker.
   Operator must verify approved worker services, task leases and separate
   source-generation capability before promising nonstop autonomous work.

## Built-in no-network contract tests

```sh
python3 -m unittest tests.test_live_pr_head_contract
```

These synthesize an isolated local Git repo, a fake private PR remote and
fixed verifier stubs. They verify malformed input denial, stale-head denial,
environment redaction, candidate dependency drift, and preservation of
untracked operator evidence. The synthetic tests do **not** contact GitHub
or run a real Laravel app. Real candidate verification must be reported
separately with its exact SHA and exit code.
