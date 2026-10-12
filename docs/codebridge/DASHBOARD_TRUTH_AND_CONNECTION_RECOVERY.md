# KMJ CodeBridge — Device & Client Dashboard Verification

## What the customer dashboard knows (and what it cannot prove)

- **Registered device:** a non-revoked, unexpired tenant-scoped Main Platform device credential. It is **not** a live heartbeat.
- **Online agent:** confirmed by the CodeBridge gateway's authorized `connection_overview` read-only diagnostic, which is not currently a part of Main Platform customer-page props. The UI says **Not verified** until authenticated heartbeat data is available; it never guesses from enrollment.
- **Authorized AI client:** a valid OAuth refresh-token family for the signed-in user. It does **not** prove the IDE is online now.
- **Permissions:** only permissions returned from the existing tenant's active KSLP plan; if none are returned, show **No permissions reported**, not synthetic READ/WRITE/EXECUTE.
- **Client revocation:** user must confirm the selected client (unique client ID suffix), then revoke refresh grants. Previously issued access tokens may live until expiry. No cross-user/client bulk deletion.

## Current read-only gateway status (2026-10-12)

The authorized gateway currently reports three online projects: KMJ-elite/Main Platform, P720/CineCore and Google VPS/CloudOS. Three older device names are granted but `connection_overview` returns `GATEWAY_REGISTRATION_MISSING`: `kmj-p720-desktop-k3ahhem`, `main-platform-kmjtechnonetgmailcom`, and `main-platform-ubuntu`. Do not delete these blindly or reauthenticate ChatGPT unnecessarily; first verify if they are retired/duplicates, or diagnose their own local services from the proper machine.

Connection Doctor: https://github.com/kmjtechno/kmj-codebridge/blob/main/docs/CONNECTION-DOCTOR.md

For the **legacy Windows P720 CodeBridge identity**, the existing safe, read-only launcher is documented at https://github.com/kmjtechno/kmj-codebridge/blob/main/docs/P720-CODEBRIDGE-DOCTOR.md. On the trusted P720 CodeBridge checkout, the owner can double-click `scripts/START-P720-CODEBRIDGE-DOCTOR.cmd` and share only its secret-free diagnostic fields. This does not change the independent CineCore agent or its uncommitted files.

## Other non-UI blockers discovered

- Quality gates **are configured** in CodeBridge even though `list_project_commands` returns `[]`. Main Platform: `fast`, `platform`, `full`. CineCore: `cinecore_configure`, `cinecore_build`, `cinecore_ctest`. CloudOS: `fast`, `full`. Custom command profiles are a separate feature; do not represent empty profiles as inability to run these configured gates.
- CineCore GitHub connector returns `GITHUB_REPOSITORY_DENIED`. This is the server's explicit GitHub repository **allowlist**, not proof of an OAuth failure. Its owner can review `CODEBRIDGE_GITHUB_REPOSITORIES` and GitHub App authorization for `kmjtechno/kmj-cinecore`. Never allow `*`, expose credentials or bypass tenant access controls. Do not change live gateway configuration without a scoped operator plan and rollback.
- The CineCore P720 checkout has multiple modified/untracked files; CloudOS on Google VPS has uncommitted files too. They belong to other engineering work. No `git reset`, `git clean`, checkout, merge or auto-format is permitted against those worktrees.

## Safe free QA of this PR

The authorized KMJ-elite `kmj-main-platform` checkout stays on `main`. Fetch the new PR head and run `scripts/ci/verify-codebridge-dashboard-pr.sh <40-character-SHA>` **from the exact pinned SHA** in a disposable worktree. It uses existing installed Node/PHP dependencies, ephemeral APP_KEY and SQLite in-memory, and runs Vite build, TypeScript and default frontend check including dashboard regressions. Do not install a paid runner or change production code for QA.

**Acceptance before merging:** frontend formatting, typecheck/build, onboarding source contracts, customer security/navigation, actual GitHub protected checks and appropriate staged browser/QA all green. Any inaccessible live connectivity remains explicitly unverified. No production deployment is authorized by this document.
