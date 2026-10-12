#!/usr/bin/env bash
# Free, exact-SHA development verification for the combined KMJ release.
# It only invokes pre-existing isolated-worktree verification scripts.
set -Eeuo pipefail

if [[ ! ${1:-} =~ ^[a-f0-9]{40}$ ]]; then
    echo "Usage: bash scripts/ci/verify-integrated-admin-licensing.sh <exact-40-char-SHA>" >&2
    exit 2
fi

sha="$1"
root="$(git rev-parse --show-toplevel)"
cd "$root"
[[ "$(basename "$root")" == "kmj-main-platform" ]] || {
    echo "BLOCKED: incorrect repository" >&2
    exit 2
}
git cat-file -e "${sha}^{commit}" || {
    echo "BLOCKED: exact PR head unavailable. Fetch the reviewed commit before running." >&2
    exit 3
}

echo "KMJ INTEGRATION_VERIFICATION_SHA=$sha"
echo "== Admin routes/UI/permissions =="
bash scripts/ci/verify-super-admin-pr.sh "$sha"

echo "== KSLP security, developer activation and SDK setup UI =="
bash scripts/ci/verify-kslp-pr.sh "$sha"

echo "PASS: exact-SHA isolated code suites for $sha"
echo "NOT VERIFIED: protected GitHub Actions, disposable PostgreSQL migration/rollback,"
echo "production signed KSLP SDKs, settlement/reconciliation, canary or production deployment"
