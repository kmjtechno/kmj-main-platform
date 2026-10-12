#!/usr/bin/env bash
# Export an exact-SHA, reviewable frontend formatting patch with existing local
# Vite+ dependencies. Never edit the production checkout or push commits.
set -Eeuo pipefail
umask 077
[[ ${1:-} =~ ^[a-f0-9]{40}$ ]] || {
    echo "Usage: bash scripts/ci/export-codebridge-format-patch.sh <exact-SHA>" >&2
    exit 2
}
sha="$1"
repo="$(git rev-parse --show-toplevel)"
[[ "$(basename "$repo")" == "kmj-main-platform" ]] || exit 2
git -C "$repo" cat-file -e "${sha}^{commit}" || {
    echo "BLOCKED: fetch exact PR head before formatting" >&2
    exit 3
}
src="$repo/apps/platform"
[[ -d "$src/node_modules" && -x "$src/node_modules/.bin/vp" ]] || {
    echo "BLOCKED: Vite+ dev dependencies absent" >&2
    exit 3
}
tmp="$(mktemp -d "${TMPDIR:-/tmp}/kmj-codebridge-format-qa.XXXXXXXX")"
cleanup() {
    git -C "$repo" worktree remove --force "$tmp/tree" >/dev/null 2>&1 || true
    rm -rf -- "$tmp"
}
trap cleanup EXIT HUP INT TERM
git -C "$repo" worktree add --detach "$tmp/tree" "$sha" >/dev/null
[[ "$(git -C "$tmp/tree" rev-parse HEAD)" == "$sha" ]] || exit 3
cp -a "$src/node_modules" "$tmp/tree/apps/platform/node_modules"
cd "$tmp/tree/apps/platform"
echo "CODEBRIDGE_FORMAT_SOURCE_SHA=$sha"
# The formatter runs only in the disposable worktree. It must not touch main.
set +e
./node_modules/.bin/vp check --fix
format_status=$?
set -e
echo "VITE_PLUS_FORMAT_EXIT=$format_status"
cd "$tmp/tree"
files=(
    apps/platform/resources/js/pages/services/codebridge.tsx
    apps/platform/scripts/check-codebridge-dashboard-truth.test.mjs
)
changed_paths="$(git diff --name-only)"
for path in $changed_paths; do
    if [[ "$path" != "${files[0]}" && "$path" != "${files[1]}" ]]; then
        echo "BLOCKED: formatter changed unexpected file $path" >&2
        exit 1
    fi
done
git diff --binary -- "${files[@]}" > "$tmp/format.patch"
if [[ ! -s "$tmp/format.patch" ]]; then
    echo "NO_FORMAT_PATCH: formatter changed no listed files"
    exit 0
fi
git diff --check -- "${files[@]}" || exit 1
echo "CODEBRIDGE_FORMAT_PATCH_SHA256=$(sha256sum "$tmp/format.patch" | cut -d' ' -f1)"
echo "CODEBRIDGE_FORMAT_PATCH_PATHS_BEGIN"
git diff --name-only -- "${files[@]}"
echo "CODEBRIDGE_FORMAT_PATCH_PATHS_END"
echo "CODEBRIDGE_FORMAT_PATCH_GZIP_BASE64_BEGIN"
gzip -9c "$tmp/format.patch" | base64 -w 76
echo
echo "CODEBRIDGE_FORMAT_PATCH_GZIP_BASE64_END"
echo "NEXT: paste or upload this output to ChatGPT for reviewed source commit."
echo "Production checkout and GitHub branch were NOT modified."
