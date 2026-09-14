#!/usr/bin/env bash
set -euo pipefail

# Official Chrome for Testing stable release, pinned for repeatable staging checks.
version='153.0.8010.36'
cache_root="${RUNNER_TOOL_CACHE:?}/kmj-staging-chrome"
release="$cache_root/$version"
chrome="$release/chrome-headless-shell"
mkdir -p "$cache_root"

if [ ! -x "$chrome" ]; then
  download_dir="$(mktemp -d "${RUNNER_TEMP:?}/kmj-chrome.XXXXXX")"
  trap 'rm -rf -- "$download_dir"' EXIT
  curl --fail --silent --show-error --retry 2 --connect-timeout 10 --max-time 180 \
    "https://storage.googleapis.com/chrome-for-testing-public/$version/linux64/chrome-headless-shell-linux64.zip" \
    --output "$download_dir/chrome.zip"
  python3 - "$download_dir" <<'PY'
import pathlib
import sys
import zipfile

root = pathlib.Path(sys.argv[1])
with zipfile.ZipFile(root / 'chrome.zip') as archive:
    archive.extractall(root)
    for item in archive.infolist():
        path = root / item.filename
        if path.is_file():
            path.chmod((item.external_attr >> 16) & 0o777 or 0o644)
PY
  mv "$download_dir/chrome-headless-shell-linux64" "$release"
fi

if ! "$chrome" --version; then
  echo 'Chrome runtime dependencies are missing; no system packages or sudo were used.' >&2
  ldd "$chrome" | grep 'not found' >&2 || true
  exit 1
fi

printf 'KMJ_STAGING_CHROME=%s\n' "$chrome" >> "${GITHUB_ENV:?}"
