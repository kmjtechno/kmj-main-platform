#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
# Verify the committed manifest digest before checking its component files.
# CONTRACT.sha256 is a raw digest, not a sha256sum --check manifest.
expected="$(cat CONTRACT.sha256)"
[[ "$expected" =~ ^[a-f0-9]{64}$ ]] || { echo 'Invalid contract digest format' >&2; exit 1; }
printf '%s  contract-files.sha256\n' "$expected" | sha256sum --check --strict -
sha256sum --check --strict contract-files.sha256
