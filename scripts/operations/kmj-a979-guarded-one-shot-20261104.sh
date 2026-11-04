#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
MODE="${1:---inspect}"
if [[ "$#" -gt 1 || ( "$MODE" != "--inspect" && "$MODE" != "--apply" ) ]]; then
  echo "KMJ_STAGE_ONE_SHOT=BLOCKED_ARGUMENTS"; exit 2
fi
if [[ "$(id -u)" != "0" || "$(hostname -s | tr '[:upper:]' '[:lower:]')" != "kmj-elite" ]]; then
  echo "KMJ_STAGE_ONE_SHOT=BLOCKED_OWNER_ROOT_HOST"; exit 2
fi
D="$(mktemp -d -p /root kmj-a979-guarded.XXXXXXXX)"
echo "KMJ_STAGE_EVIDENCE_DIRECTORY=$D"
curl --proto '=https' --tlsv1.2 -fLSs --retry 2   "https://raw.githubusercontent.com/kmjtechno/kmj-main-platform/1e2ab0f4a7cfee0746b48d9b9295db9ee89c4774/scripts/operations/KMJ_STAGE_A979_ISOLATED_MIGRATIONS_20261104.py"   -o "$D/migrate.py"
curl --proto '=https' --tlsv1.2 -fLSs --retry 2   "https://raw.githubusercontent.com/kmjtechno/kmj-main-platform/6a18b9c7a407d787a9eef40aa92d7d1f75560d32/scripts/operations/KMJ_STAGE_VHOST_ROUTE_PREFLIGHT_20261104.py"   -o "$D/vhost.py"
printf '%s  %s\n'   "bd52f881e74f2464bd25194cd44ec17e5e87a50910c5c2e9ed8fa976588cf881" "$D/migrate.py"   "c95d67b00543528ae193aee421ea282e9def3d97fe8c40cc27edb2a52a8a69a2" "$D/vhost.py" | sha256sum --check --status
echo "KMJ_STAGE_PINNED_SOURCE=PASS"
python3 -I -B "$D/vhost.py" | tee "$D/vhost.receipt"
grep -qx 'LIVE_POINTERS=EXPECTED' "$D/vhost.receipt"
grep -qx 'STAGING_VHOST_SOURCE_TRUST=ROOT_TRUSTED' "$D/vhost.receipt"
grep -qx 'NGINX_CONFIG_SYNTAX=PASS' "$D/vhost.receipt"
grep -qx 'PHP_FPM_CONFIG_SYNTAX=PASS' "$D/vhost.receipt"
python3 -I -B "$D/migrate.py" --inspect | tee "$D/migration-inspect.receipt"
grep -qx 'KMJ_STAGE_A979_MIGRATIONS=READ_ONLY_READY' "$D/migration-inspect.receipt"
if [[ "$MODE" == "--inspect" ]]; then
  echo "KMJ_STAGE_ONE_SHOT=PASS_READ_ONLY_NO_MIGRATION"; exit 0
fi
python3 -I -B "$D/migrate.py" --apply | tee "$D/migration-apply.receipt"
grep -qx 'KMJ_STAGE_A979_MIGRATIONS=PASS_CANDIDATE_DB_SCHEMA_ONLY' "$D/migration-apply.receipt"
echo "KMJ_STAGE_ONE_SHOT=PASS_ISOLATED_DB_ONLY_NOT_LIVE"
