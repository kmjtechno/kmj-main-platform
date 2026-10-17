#!/usr/bin/env bash
# KMJ zero-additional-cost development QA on the *current* PR HEAD.
# Uses only reviewed exact-SHA, disposable-worktree verifier entrypoints.
# Does not change protected GitHub checks, branch state, production DB or DNS.
set -Eeuo pipefail
umask 077

usage() {
  echo "Usage: bash scripts/ci/verify-live-pr-head.sh <PR-number> <40-hex-head-SHA> <frontend|admin|postgres>" >&2
  exit 2
}

[[ $# -eq 3 ]] || usage
pr="$1"
sha="$2"
profile="$3"
[[ "$pr" =~ ^[1-9][0-9]{0,5}$ ]] || usage
[[ "$sha" =~ ^[0-9a-f]{40}$ ]] || usage

case "$profile" in
  frontend) verifier="scripts/ci/verify-codebridge-dashboard-pr.sh" ;;
  admin) verifier="scripts/ci/verify-super-admin-pr.sh" ;;
  postgres) verifier="scripts/ci/verify-postgres-staging.sh" ;;
  *) usage ;;
esac

[[ "$(id -u)" != 0 ]] || { echo 'BLOCKED: use unprivileged repository owner, not root' >&2; exit 3; }
repo="$(git rev-parse --show-toplevel)"
[[ "$(basename "$repo")" == 'kmj-main-platform' ]] || { echo 'BLOCKED: incorrect repository' >&2; exit 3; }
[[ "$(git -C "$repo" symbolic-ref --quiet --short HEAD)" == 'main' ]] || {
  echo 'BLOCKED: invoke the pinned verifier from the main checkout' >&2; exit 3;
}
[[ -z "$(git -C "$repo" status --porcelain --untracked-files=no)" ]] || {
  echo 'BLOCKED: tracked main checkout has uncommitted changes' >&2; exit 3;
}
[[ -f "$repo/$verifier" && ! -L "$repo/$verifier" ]] || {
  echo 'BLOCKED: missing or linked approved verifier' >&2; exit 3;
}
git -C "$repo" ls-files --error-unmatch "$verifier" >/dev/null
[[ -z "$(git -C "$repo" diff -- "$verifier")" ]] || {
  echo 'BLOCKED: verifier has uncommitted changes' >&2; exit 3;
}
remote="$(git -C "$repo" remote get-url origin)"
case "$remote" in
  https://github.com/kmjtechno/kmj-main-platform|https://github.com/kmjtechno/kmj-main-platform.git|git@github.com:kmjtechno/kmj-main-platform|git@github.com:kmjtechno/kmj-main-platform.git) ;;
  *) echo 'BLOCKED: origin is not the approved private KMJ Main Platform repository' >&2; exit 3 ;;
esac

baseline_ref='refs/heads/main'
remote_main="$(git -C "$repo" ls-remote --exit-code origin "$baseline_ref" | awk -v wanted="$baseline_ref" '$2 == wanted { print $1 }')"
local_main="$(git -C "$repo" rev-parse HEAD)"
[[ "$remote_main" =~ ^[0-9a-f]{40}$ && "$remote_main" == "$local_main" ]] || {
  echo 'BLOCKED: baseline main checkout is not the current protected remote main SHA' >&2
  exit 3
}

head_ref="refs/pull/$pr/head"
remote_head="$(git -C "$repo" ls-remote --exit-code origin "$head_ref" | awk -v wanted="$head_ref" '$2 == wanted { print $1 }')"
[[ "$remote_head" =~ ^[a-f0-9]{40}$ ]] || {
  echo 'BLOCKED: cannot verify the private PR head' >&2; exit 3;
}
[[ "$remote_head" == "$sha" ]] || {
  echo "BLOCKED: PR head advanced or expected SHA incorrect; actual=$remote_head" >&2; exit 3;
}
if ! git -C "$repo" cat-file -e "$sha^{commit}" 2>/dev/null; then
  # Fetch only object data. Do not change HEAD, local branches, tracked files,
  # or existing untracked QA results.
  git -C "$repo" fetch --no-tags --no-write-fetch-head origin "$head_ref" >/dev/null || {
    echo 'BLOCKED: cannot fetch approved exact PR object' >&2; exit 3;
  }
fi
git -C "$repo" cat-file -e "$sha^{commit}" || {
  echo 'BLOCKED: exact PR object not available' >&2; exit 3;
}

# Existing verifier scripts intentionally copy dependencies from the stable
# main checkout. Reuse is valid only if both lockfiles are identical.
for lock in apps/platform/composer.lock apps/platform/package-lock.json; do
  main_lock="$(git -C "$repo" show "HEAD:$lock" | sha256sum | awk '{print $1}')"
  pr_lock="$(git -C "$repo" show "$sha:$lock" | sha256sum | awk '{print $1}')"
  [[ "$main_lock" == "$pr_lock" ]] || {
    echo "BLOCKED: $lock differs; preinstalled main dependencies cannot verify this PR" >&2
    exit 3
  }
done

scratch="$(mktemp -d /tmp/kmj-live-pr-qa.XXXXXXXX)"
trap 'rm -rf -- "$scratch"' EXIT
mkdir -m 700 "$scratch/home" "$scratch/tmp"

echo "QA_PROFILE=$profile"
echo "QA_PR=$pr"
echo "QA_VERIFIED_REMOTE_HEAD=$sha"
echo 'QA_SCOPE=isolated-worktree'
echo 'QA_PRODUCTION_DB=UNTOUCHED'
echo 'QA_GITHUB_ACTIONS_STATUS=NOT_VERIFIED'
# Clearing the environment ensures the candidate's PHP/build tools do not
# inherit production database credentials, provider tokens, SSH agent or
# deployment secrets. The called script creates a disposable app .env.
env -i \
  PATH="$PATH" HOME="$scratch/home" TMPDIR="$scratch/tmp" LANG=C.UTF-8 \
  bash "$repo/$verifier" "$sha"
echo "QA_LOCAL_EXACT_SHA=PASS $sha"
echo 'QA_HOSTED_REQUIRED_CHECKS=NOT_REPLACED'
