#!/usr/bin/env bash
set -euo pipefail
: "${KMJ_CONTROLLER_URL:?Set KMJ_CONTROLLER_URL}"
curl -fsS -X POST "$KMJ_CONTROLLER_URL/start" \
  -H 'content-type: application/json' \
  -d '{"requested_by":"owner-mobile","dry_run":true}'
