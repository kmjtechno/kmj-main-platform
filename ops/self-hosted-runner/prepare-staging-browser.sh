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

# Minimal Ubuntu images can lack Chrome's desktop shared libraries. Extract
# authenticated distro packages into this private cache; never install them.
if ! "$chrome" --version >/dev/null 2>&1 && [ ! -d "$release/runtime-libs" ]; then
  dependency_dir="$(mktemp -d "${RUNNER_TEMP:?}/kmj-chrome-libs.XXXXXX")"
  (
    trap 'rm -rf -- "$dependency_dir"' EXIT
    . /etc/os-release
    test "$ID" = ubuntu
    test "$VERSION_ID" = 24.04
    mkdir -p "$dependency_dir/packages" "$dependency_dir/root"
    cd "$dependency_dir/packages"
    apt-get download \
      libatk1.0-0t64 libatk-bridge2.0-0t64 libatspi2.0-0t64 \
      libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
      libgbm1 libdrm2 libwayland-server0 libasound2t64 libasound2-data
    for package in ./*.deb; do
      dpkg-deb --extract "$package" "$dependency_dir/root"
    done
    mv "$dependency_dir/root" "$release/runtime-libs"
  )
fi

wrapper="$release/kmj-chrome"
cat > "$wrapper" <<'BROWSER'
#!/usr/bin/env bash
set -euo pipefail
browser_root="$(cd -- "$(dirname -- "$0")" && pwd)"
export LD_LIBRARY_PATH="$browser_root/runtime-libs/usr/lib/x86_64-linux-gnu:$browser_root/runtime-libs/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$browser_root/chrome-headless-shell" "$@"
BROWSER
chmod 700 "$wrapper"
"$wrapper" --version
printf 'KMJ_STAGING_CHROME=%s\n' "$wrapper" >> "${GITHUB_ENV:?}"
