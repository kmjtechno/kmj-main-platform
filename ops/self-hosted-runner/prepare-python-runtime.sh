#!/usr/bin/env bash
set -euo pipefail

repo_root="${GITHUB_WORKSPACE:-$(pwd)}"
requirements="$repo_root/requirements.txt"
python_bin=""

declare -a candidates=()
if [ -n "${RUNNER_TOOL_CACHE:-}" ]; then
  for candidate in "${RUNNER_TOOL_CACHE}"/Python/3.13*/x64/bin/python3; do
    [ -x "$candidate" ] && candidates+=("$candidate")
  done
fi
for candidate in /opt/kmj-actions-runner*/_work/_tool/Python/3.13*/x64/bin/python3; do
  [ -x "$candidate" ] && candidates+=("$candidate")
done

if [ "${#candidates[@]}" -gt 0 ]; then
  python_bin="$(printf '%s\n' "${candidates[@]}" | sort -Vu | tail -n 1)"
fi

if [ -z "$python_bin" ]; then
  python_bin="$(command -v python3 || true)"
fi

if [ -z "$python_bin" ]; then
  echo 'KMJ Python runtime unavailable: python3 is required.' >&2
  exit 20
fi
"$python_bin" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit(f'Python 3.11+ required, found {sys.version.split()[0]}')
print(f'KMJ reusable Python {sys.version.split()[0]} detected')
PY

check_imports() {
  "$1" - <<'PY'
import fastapi, httpx, pydantic, yaml
print('KMJ Python controller dependencies ready')
PY
}

if ! check_imports "$python_bin"; then
  if ! "$python_bin" -m pip --version >/dev/null 2>&1; then
    echo 'KMJ Python dependencies are missing and the selected runtime has no pip.' >&2
    echo 'Pre-provision the shared cached Python runtime instead of downloading setup-python per job.' >&2
    exit 21
  fi

  lock_root="${RUNNER_TEMP:-/tmp}/kmj-python-runtime"
  mkdir -p "$lock_root"
  (
    flock -x 9
    if ! check_imports "$python_bin"; then
      "$python_bin" -m pip install --disable-pip-version-check --retries 3 --timeout 30 -r "$requirements"
      check_imports "$python_bin"
    fi
  ) 9>"$lock_root/.prepare.lock"
fi
runtime_bin="$(dirname "$python_bin")"
echo "$runtime_bin" >> "${GITHUB_PATH:?GITHUB_PATH is required}"
echo "KMJ cached Python runtime ready: $python_bin"
