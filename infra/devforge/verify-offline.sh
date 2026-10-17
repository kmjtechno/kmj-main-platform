#!/usr/bin/env bash
# Independent no-network source contract verification. No Docker, root or npm required.
set -Eeuo pipefail
here="$(cd "$(dirname "$0")" && pwd -P)"
repo="$(cd "$here/../.." && pwd -P)"

bash -n "$here/bootstrap-kmj-elite.sh"
echo "BOOTSTRAP_BASH_SYNTAX=PASS"

python3 -B - "$here/devforge-broker.py" <<'PY'
import ast
import pathlib
import sys
p = pathlib.Path(sys.argv[1])
ast.parse(p.read_text(encoding="utf8"), filename=str(p))
print("BROKER_PYTHON_SYNTAX=PASS")
PY

python3 -B -m unittest discover -s "$here" -p 'test_devforge_broker.py' -v
echo "BROKER_BOUNDARY_TESTS=PASS"

if command -v php >/dev/null 2>&1; then
  for p in \
    "$repo/apps/platform/app/Services/DevForge/DevForgeBrokerClient.php" \
    "$repo/apps/platform/routes/devforge-admin.php" \
    "$repo/apps/platform/tests/Feature/DevForgeOwnerControlTest.php"; do
    php -l "$p" >/dev/null
  done
  echo "PHP_SYNTAX=PASS"
else
  echo "PHP_SYNTAX=NOT_RUN missing_php"
fi

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  # Do not require the root-owned, not-yet-provisioned production Compose file.
  echo "DOCKER_COMPOSE_CLI=AVAILABLE"
else
  echo "DOCKER_COMPOSE_CLI=UNAVAILABLE"
fi

echo "DEVFORGE_OFFLINE_SOURCE_QA=PASS"
echo "FRONTEND_BUILD=NOT_RUN"
echo "LARAVEL_FEATURE_TESTS=NOT_RUN"
echo "HOST_BROKER_LIVE_TEST=NOT_RUN"
echo "LIVE_GIT_HEALTH=NOT_RUN"
