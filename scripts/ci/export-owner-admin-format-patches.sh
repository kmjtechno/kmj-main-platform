#!/usr/bin/env bash
# Free, unprivileged exact-commit formatter diagnostics for KMJ Main Platform.
# Output is source-only patches readable through authorized CodeBridge.
set -Eeuo pipefail
umask 077

die() { printf 'KMJ_FORMAT_BLOCKED=%s\n' "$1" >&2; exit 1; }
[[ $# == 1 ]] || die EXACT_SHA_REQUIRED
[[ "$(id -u)" != 0 ]] || die RUN_AS_UNPRIVILEGED_PROJECT_OWNER
[[ "$1" =~ ^[a-f0-9]{40}$ ]] || die EXACT_SHA_REQUIRED
SHA="$1"
for cmd in git php node npm python3 mktemp cp stat sha256sum; do
  command -v "$cmd" >/dev/null || die "MISSING_$cmd"
done
ROOT="$(git rev-parse --show-toplevel)"
[[ "$(basename "$ROOT")" == kmj-main-platform ]] || die WRONG_REPOSITORY
[[ -d "$ROOT/work" && ! -L "$ROOT/work" ]] || die APPROVED_WORK_DIR_MISSING
[[ "$(stat -c %u "$ROOT/work")" == "$(id -u)" ]] || die WORK_DIR_OWNERSHIP
git -C "$ROOT" cat-file -e "$SHA^{commit}" || die PINNED_COMMIT_NOT_FETCHED
[[ -d "$ROOT/apps/platform/vendor" && -d "$ROOT/apps/platform/node_modules" ]] ||
  die DEVELOPMENT_DEPENDENCIES_MISSING

TEMP="$(mktemp -d "$ROOT/work/kmj-admin-format-XXXXXXXX")"
WORKTREE="$TEMP/tree"
clean() {
  git -C "$ROOT" -c core.hooksPath=/dev/null worktree remove --force "$WORKTREE" >/dev/null 2>&1 || true
  rm -rf -- "$TEMP"
}
trap clean EXIT HUP INT TERM

GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null \
  git -C "$ROOT" -c core.hooksPath=/dev/null worktree add --detach "$WORKTREE" "$SHA"
[[ "$(git -C "$WORKTREE" rev-parse HEAD)" == "$SHA" ]] || die WRONG_WORKTREE_HEAD

# Never copy or source .env, production credentials or live app configuration.
[[ ! -e "$WORKTREE/apps/platform/.env" ]] || die UNEXPECTED_ENV_FILE
cp -a -- "$ROOT/apps/platform/vendor" "$WORKTREE/apps/platform/vendor"
cp -a -- "$ROOT/apps/platform/node_modules" "$WORKTREE/apps/platform/node_modules"
cd "$WORKTREE/apps/platform"
npm run check:fix || die FRONTEND_FORMAT_FAILED
./vendor/bin/pint || die PHP_FORMAT_FAILED
cd "$WORKTREE"
[[ "$(git rev-parse HEAD)" == "$SHA" ]] || die HEAD_CHANGED

PATCHES="$ROOT/work/qa/admin-402/$SHA"
for ancestor in "$ROOT/work" "$ROOT/work/qa" "$ROOT/work/qa/admin-402"; do
  if [[ -e "$ancestor" || -L "$ancestor" ]]; then
    [[ -d "$ancestor" && ! -L "$ancestor" &&
      "$(stat -c %u "$ancestor")" == "$(id -u)" ]] || die UNSAFE_PATCH_DIRECTORY
  fi
done
[[ ! -e "$PATCHES" && ! -L "$PATCHES" ]] || die PATCH_OUTPUT_ALREADY_EXISTS
mkdir -p -m 0700 "$PATCHES"
count=0
manifest="$PATCHES/manifest.txt"
printf 'SOURCE_SHA=%s\nREPO=%s\n' "$SHA" kmjtechno/kmj-main-platform > "$manifest"
while IFS= read -r -d '' changed; do
  case "$changed" in
    apps/platform/*.php|apps/platform/resources/js/*|apps/platform/tests/*.php|apps/platform/tests/Feature/*.php|packages/domain-*/*.php|packages/domain-*/database/migrations/*.php)
      ;;
    *) die "UNEXPECTED_FORMAT_PATH_$changed" ;;
  esac
  count=$((count + 1))
  [[ $count -le 50 ]] || die TOO_MANY_FILES
  artifact="$(printf '%03d.patch' "$count")"
  git diff --no-ext-diff -- "$changed" > "$PATCHES/$artifact"
  bytes="$(stat -c %s "$PATCHES/$artifact")"
  [[ $bytes -gt 0 && $bytes -le 100000 ]] || die PATCH_SIZE_INVALID
  printf '%s %s %s\n' "$artifact" "$bytes" "$changed" >> "$manifest"
done < <(git diff --name-only -z --)

# These are static checks of the detached source, never production operations.
export APP_ENV=testing DB_CONNECTION=sqlite DB_DATABASE=:memory:
export QUEUE_CONNECTION=sync CACHE_STORE=array SESSION_DRIVER=array
export MAIL_MAILER=array
cd "$WORKTREE/apps/platform"
for check in frontend types phpstan; do
  case "$check" in
    frontend) args=(npm run check) ;;
    types) args=(npm run types:check) ;;
    phpstan) args=(./vendor/bin/phpstan analyse --no-progress --memory-limit=1G) ;;
  esac
  if "${args[@]}" > "$PATCHES/$check.log" 2>&1; then
    printf '%s=PASS\n' "$check" >> "$manifest"
  else
    printf '%s=FAIL\n' "$check" >> "$manifest"
  fi
  truncate -s 100000 "$PATCHES/$check.log"
done

# Keep raw formatter/compiler output local. Generate a bounded, printable,
# secret-scrubbed text summary for CodeBridge's strict UTF-8 reader.
python3 - "$PATCHES" <<'PY'
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
ansi = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")
redactions = [
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)\S+"),
    re.compile(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"(?i)(?:gh[pousr]_|github_pat_|sk-proj-|sk-)[A-Za-z0-9_-]{12,}"),
]
for name in ("frontend", "types", "phpstan"):
    src = root / (name + ".log")
    raw = src.read_bytes()
    value = ansi.sub("", raw.decode("utf-8", "replace"))
    value = "".join(c if c in "\n\t" or ord(c) >= 32 else " " for c in value)
    for i, pattern in enumerate(redactions):
        value = pattern.sub(r"\1[REDACTED]" if i < 2 else "[REDACTED]", value)
    (root / (name + ".txt")).write_text(value[-32000:], encoding="utf-8")
PY
cd "$ROOT"

echo "KMJ_ADMIN_FORMAT_SHA=$SHA"
echo "KMJ_ADMIN_FORMAT_PATCH_DIR=work/qa/admin-402/$SHA"
echo "KMJ_ADMIN_FORMAT_PATCH_COUNT=$count"
echo "KMJ_ADMIN_FORMAT_DONE=1"
echo "The main checkout, DB, billing, DNS and live app have not been modified."
