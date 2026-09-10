#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

# Planned migration/export helper.
# This does NOT replace off-server backups; copy the resulting archive to a different system/provider.

SITE_USER="${KMJ_SITE_USER:-kmjstage}"
DB_NAME="${KMJ_DB_NAME:-kmj_platform_staging}"
DB_USER="${KMJ_DB_USER:-kmj_platform}"
SECRETS="/root/.kmj-server-secrets"

[[ $EUID -eq 0 ]] || { echo "Run as root."; exit 1; }

# New servers use the canonical root secrets file. The original staging VPS
# predates that file, so fall back to its existing server-local deploy env.
if [[ -f "$SECRETS" ]]; then
  # shellcheck disable=SC1090
  source "$SECRETS"
elif [[ -f "/home/$SITE_USER/.kmj-stage-env" ]]; then
  # shellcheck disable=SC1090
  source "/home/$SITE_USER/.kmj-stage-env"
  DB_NAME="${KMJ_DB_DATABASE:-$DB_NAME}"
  DB_USER="${KMJ_DB_USERNAME:-$DB_USER}"
else
  echo "No server-local database credential source found."
  exit 2
fi

[[ -n "${KMJ_DB_PASSWORD:-}" ]] || { echo "Database password is unavailable."; exit 3; }

ts="$(date +%Y%m%d-%H%M%S)"
work="/root/kmj-migration-$ts"
archive="/root/KMJ_MAIN_PLATFORM_MIGRATION_$ts.tar.gz"
mkdir -p "$work"

echo "Exporting PostgreSQL..."
PGPASSWORD="$KMJ_DB_PASSWORD" pg_dump \
  -h 127.0.0.1 -U "$DB_USER" -d "$DB_NAME" \
  --format=custom --file="$work/database.dump"

repo="/home/$SITE_USER/repos/kmj-main-platform"
app="$repo/apps/platform"

if [[ -d "$app/storage/app" ]]; then
  echo "Exporting application-managed files..."
  tar -C "$app" -czf "$work/storage-app.tar.gz" storage/app
fi

cat > "$work/manifest.txt" <<EOF
created_at=$(date -Is)
hostname=$(hostname)
kernel=$(uname -r)
postgres=$(/usr/lib/postgresql/18/bin/psql --version 2>/dev/null || true)
php=$(php8.5 -r 'echo PHP_VERSION;' 2>/dev/null || true)
node=$(sudo -u "$SITE_USER" -H bash -lc 'export NVM_DIR="$HOME/.nvm"; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"; node -v 2>/dev/null || true')
rust=$(sudo -u "$SITE_USER" -H bash -lc '[ -f "$HOME/.cargo/env" ] && . "$HOME/.cargo/env"; rustc --version 2>/dev/null || true')
live_commit=$(cat "/home/$SITE_USER/.kmj-stage-last-success" 2>/dev/null || true)
deploy_branch=$(grep '^BRANCH=' "/home/$SITE_USER/bin/kmj-stage-deploy.sh" 2>/dev/null | head -1 || true)
EOF

tar -C "$(dirname "$work")" -czf "$archive" "$(basename "$work")"
sha256sum "$archive" > "$archive.sha256"
rm -rf "$work"

echo
echo "Migration export created:"
echo "$archive"
echo "$archive.sha256"
echo
echo "IMPORTANT: copy BOTH files off this VPS. A local-only export is not disaster recovery."
