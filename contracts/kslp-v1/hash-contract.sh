#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
: > contract-files.sha256
for f in README.md entitlement.schema.json error-codes.json gates.json evidence-manifest.schema.json; do sha256sum "$f" >> contract-files.sha256; done
sha256sum contract-files.sha256 | cut -d" " -f1 > CONTRACT.sha256
