# KMJ-elite — Safe PR #375 Release Preflight

**Draft release candidate: not production deployment.** Resolve Git safe-ownership failures by executing the checks as the repository owner, never by chown -R or wildcard safe.directory.

From a root shell on the authorized KMJ-elite server, run this single block:

```bash
set -Eeuo pipefail
REPO=/srv/kmj-codebridge-projects/kmj-main-platform
test -d "$REPO/.git" || { echo 'BLOCKED: expected Git directory missing'; exit 2; }
OWNER="$(stat -c %U "$REPO/.git")"
test "$OWNER" != root && test "$OWNER" != UNKNOWN || { echo 'BLOCKED: unexpected Git owner'; exit 2; }
OWNER_HOME="$(getent passwd "$OWNER" | cut -d: -f6)"
test -d "$OWNER_HOME" || { echo 'BLOCKED: owner home missing'; exit 2; }
runuser -u "$OWNER" -- env HOME="$OWNER_HOME" REPO="$REPO" bash -c '
  set -Eeuo pipefail
  cd "$REPO"
  git status --short
  git fetch --no-tags origin pull/375/head
  SHA="$(git rev-parse --verify FETCH_HEAD^{commit})"
  echo "VERIFYING_PR_375_SHA=$SHA"
  git show "$SHA:scripts/ci/verify-integrated-admin-licensing.sh" |
    bash -s -- "$SHA"
'
```

This script fetches the PR (but never checks it out on main) and runs an exact-SHA disposable worktree preflight. A wrong filesystem owner, missing dependency, failed test, or missing PHP extension results in BLOCKED/FAIL. Do not run tests as root or change the production DB.

**What PASS does and does not mean:** PHP source syntax, built-in Node contract checks, isolated Laravel/TS/static gates are distinct. GitHub protected CI, PostgreSQL staged migration and rollback, full multi-product signed KSLP SDK interoperability, paid-order settlement and operator/browser canary must each pass separately before merge and production deployment.

Do not enable KMJ_DEVELOPER_LICENSING_ENABLED until independently verified client lease signing and revocation/renewal are ready. No paid services or protection bypasses.
