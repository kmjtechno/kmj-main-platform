#!/usr/bin/env bash
# CI-only: application HTTP + database migration/rollback rehearsal of
# BASE (previous release code) vs HEAD (candidate) on a disposable PG18.
# Private unix socket, --network none, no production DB or credentials.
set -Eeuo pipefail
umask 077

(( $# == 2 )) || { echo 'BLOCKED: expected BASE_SHA HEAD_SHA'; exit 2; }
base="$1"; head="$2"
[[ "$base" =~ ^[0-9a-f]{40}$ && "$head" =~ ^[0-9a-f]{40}$ ]] || { echo 'BLOCKED: invalid SHA'; exit 2; }
[[ "${GITHUB_ACTIONS:-}" == true && -n "${RUNNER_TEMP:-}" ]] || { echo 'BLOCKED: GitHub-hosted CI context required'; exit 2; }
[[ "$(id -u)" != 0 ]] || { echo 'BLOCKED: root runner not allowed'; exit 2; }
repo="$(git rev-parse --show-toplevel)"
[[ "$(git -C "$repo" rev-parse HEAD)" == "$head" ]] || { echo 'BLOCKED: wrong candidate SHA'; exit 2; }
[[ -z "$(git -C "$repo" status --porcelain)" ]] || { echo 'BLOCKED: dirty checkout'; exit 2; }
for tool in docker php python3 composer psql git; do
  command -v "$tool" >/dev/null || { echo "BLOCKED: missing $tool"; exit 3; }
done
command -v npm >/dev/null || { echo 'BLOCKED: missing npm'; exit 3; }
php -r 'exit(extension_loaded("pdo_pgsql") ? 0 : 1);' || { echo 'BLOCKED: pdo_pgsql missing'; exit 3; }

image='postgres:18.6-alpine3.24@sha256:10a5c69a83035ab5239f5620d708520e8b28f5aa1f2b20143e6024532edadfb5'
tmp="$(mktemp -d "$RUNNER_TEMP/kmj-app-rollback.XXXXXXXX")"
socket="$tmp/socket"; mkdir -m 0700 "$socket"
container_name='kmj-app-rollback-ci'
cleanup() {
  docker rm -f "$container_name" >/dev/null 2>&1 || true
  git -C "$repo" worktree remove --force "$tmp/previous" >/dev/null 2>&1 || true
  git -C "$repo" worktree prune >/dev/null 2>&1 || true
  if [[ -d "$socket" && ! -L "$socket" && "$socket" == "$tmp/socket" ]]; then
    sudo chown "$(id -u):$(id -g)" "$socket" || true
    chmod 0700 "$socket" || true
  fi
  rm -rf -- "$tmp"
}
trap cleanup EXIT

# Previous release code in its own worktree; candidate is the checked-out HEAD.
git -C "$repo" cat-file -e "$base^{commit}" || { echo 'BLOCKED: base commit unavailable'; exit 3; }
git -C "$repo" worktree add --detach "$tmp/previous" "$base" >/dev/null
for tree in "$tmp/previous/apps/platform" "$repo/apps/platform"; do
  test ! -e "$tree/.env" && test ! -L "$tree/.env" || { echo 'BLOCKED: .env present'; exit 2; }
  ( cd "$tree" && composer install --no-interaction --prefer-dist --no-progress --optimize-autoloader >/dev/null \
      && npm ci --no-audit --no-fund >/dev/null 2>&1 && npm run build >/dev/null 2>&1 \
      && test -s public/build/manifest.json ) || { echo 'BLOCKED: tree dependencies/frontend build failed'; exit 3; }
done

docker pull "$image" >/dev/null
pg_uid="$(docker run --rm --network none --entrypoint id "$image" -u postgres)"
[[ "$pg_uid" =~ ^[0-9]{1,6}$ ]] || { echo 'BLOCKED: unrecognized PostgreSQL UID'; exit 3; }
chmod 0770 "$socket"
sudo chown "$pg_uid:$(id -g)" "$socket"
docker run -d --name "$container_name" --network none \
  -e POSTGRES_USER=kmj_qa -e POSTGRES_DB=kmj_release_qa \
  -e POSTGRES_PASSWORD=ephemeral-ci-only \
  -e POSTGRES_INITDB_ARGS='--auth-local=trust --auth-host=reject' \
  --mount "type=bind,src=$socket,dst=/var/run/postgresql" \
  "$image" -c listen_addresses='' -c unix_socket_directories=/var/run/postgresql \
  -c unix_socket_permissions=0777 >/dev/null

ready=0
for _ in $(seq 1 90); do
  if [[ -S "$socket/.s.PGSQL.5432" ]] && psql -h "$socket" -X -qAt -v ON_ERROR_STOP=1 \
      -U kmj_qa -d kmj_release_qa -c 'SELECT 1' >/dev/null 2>&1; then ready=1; break; fi
  sleep 1
done
[[ "$ready" == 1 ]] || { echo 'APP_ROLLBACK_PG18_START=FAIL'; docker logs --tail 40 "$container_name" 2>&1 || true; exit 1; }
ver="$(psql -h "$socket" -X -qAt -U kmj_qa -d kmj_release_qa -c 'SHOW server_version_num')"
(( ver / 10000 == 18 )) || { echo 'BLOCKED: not PostgreSQL 18'; exit 3; }
[[ "$(psql -h "$socket" -X -qAt -U kmj_qa -d kmj_release_qa -c "SELECT count(*) FROM pg_tables WHERE schemaname='public'")" == 0 ]] \
  || { echo 'BLOCKED: database not empty'; exit 3; }
echo "APP_ROLLBACK_BASE_SHA=$base"
echo "APP_ROLLBACK_HEAD_SHA=$head"
echo 'APP_ROLLBACK_DATABASE=ISOLATED_PRIVATE_UNIX_SOCKET NETWORK=NONE HOST_PORTS=NONE'

# The orchestrator builds its own clean child environment (no inherited secrets).
env -i PATH="$PATH" HOME="$tmp" \
  DB_HOST="$socket" DB_PORT=5432 DB_DATABASE=kmj_release_qa DB_USERNAME=kmj_qa DB_PASSWORD= \
  KMJ_REHEARSAL_PREVIOUS_APP="$tmp/previous/apps/platform" \
  KMJ_REHEARSAL_CANDIDATE_APP="$repo/apps/platform" \
  KMJ_REHEARSAL_VERBOSE=1 \
  python3 -I "$repo/scripts/operations/rehearse-app-http-db-rollback-20261029.py"
echo 'PRODUCTION_DATABASE_TOUCHED=NO PRODUCTION_DEPLOYMENT=NONE'
