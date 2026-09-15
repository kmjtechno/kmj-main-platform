#!/usr/bin/env bash
set -euo pipefail

version=1.18.31
client_dir="${RUNNER_TOOL_CACHE:?}/kmj-opencode/$version"
if [ ! -x "$client_dir/opencode" ]; then
  temporary="$(mktemp -d "${RUNNER_TEMP:?}/kmj-opencode-install.XXXXXX")"
  trap 'rm -rf -- "$temporary"' EXIT
  curl --fail --silent --show-error --location --retry 2 --max-time 120 \
    'https://github.com/anomalyco/opencode/releases/download/v1.18.31/opencode-linux-x64-baseline.tar.gz' \
    --output "$temporary/opencode.tar.gz"
  printf 'b283e8dbe9e6fc224bb4b79992ce3bd2174b8b7b0c3e7d1b4e6024a1d11edc84  %s\n' \
    "$temporary/opencode.tar.gz" | sha256sum --check -
  tar --no-same-owner -xzf "$temporary/opencode.tar.gz" -C "$temporary" opencode
  mkdir -p "$client_dir"
  install -m 755 "$temporary/opencode" "$client_dir/opencode"
fi
test "$("$client_dir/opencode" --version)" = "$version"
echo "KMJ_OPENCODE_BINARY=$client_dir/opencode" >> "$GITHUB_ENV"
echo 'KMJ_OPENCODE_FREE_ENABLED=true' >> "$GITHUB_ENV"
echo "Official OpenCode client $version ready; local inference is not used."
