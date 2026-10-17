#!/usr/bin/env bash
# One-time owner-approved bootstrap. Thereafter use Super Admin /operator/devforge.
# Usage: sudo env DEVFORGE_WEB_USER=www-data bash infra/devforge/bootstrap-kmj-elite.sh
set -Eeuo pipefail
umask 077
die() { printf 'DEVFORGE_BOOTSTRAP=BLOCKED reason=%s\n' "$1" >&2; exit 1; }

test "$(id -u)" -eq 0 || die ROOT_REQUIRED
test "$(hostname)" = KMJ-elite || die NOT_KMJ_ELITE
web_user="$(printenv DEVFORGE_WEB_USER || :)"
test -n "$web_user" || web_user=www-data
[[ "$web_user" =~ ^[a-z_][a-z0-9_-]{0,31}$ ]] || die INVALID_WEB_USER
id "$web_user" >/dev/null 2>&1 || die WEB_USER_NOT_FOUND
for tool in python3 docker systemctl install getent; do
  command -v "$tool" >/dev/null || die "MISSING_$tool"
done
docker info >/dev/null 2>&1 || die DOCKER_ENGINE_UNAVAILABLE
docker compose version >/dev/null 2>&1 || die COMPOSE_V2_UNAVAILABLE

src="$(cd -- "$(dirname -- "$0")" && pwd -P)/devforge-broker.py"
test -f "$src" && test ! -L "$src" || die BROKER_SOURCE_MISSING
python3 -c 'import ast,sys; ast.parse(open(sys.argv[1],encoding="utf8").read())' "$src" || die BROKER_INVALID

base=/opt/kmj-devforge
state=/var/lib/kmj-devforge
unit=/etc/systemd/system/kmj-devforge-broker.service
broker=/usr/local/libexec/kmj-devforge-broker.py

# No silent overwrite of a different installation or service.
test ! -L "$base" && test ! -L "$state" || die DIRECTORY_SYMLINK
test ! -e "$unit" || die BROKER_ALREADY_PROVISIONED
test ! -e "$broker" || die BROKER_BINARY_EXISTS
test ! -e "$base/compose.yaml" || die COMPOSE_ALREADY_EXISTS
test ! -e /run/kmj-devforge/control.sock || die SOCKET_ALREADY_EXISTS

install -d -o root -g root -m 0755 /usr/local/libexec "$base"
install -d -o root -g root -m 0700 "$state"
install -d -o 1000 -g 1000 -m 0700 "$base/data" "$base/config"
install -o root -g root -m 0700 "$src" "$broker"

cat > "$base/compose.yaml" <<'COMPOSE'
name: kmj-devforge
services:
  server:
    image: docker.gitea.com/gitea:1.27.3-rootless
    container_name: kmj-devforge-server
    restart: unless-stopped
    environment:
      GITEA__server__ROOT_URL: "http://localhost:3030/"
      GITEA__server__SSH_DOMAIN: "localhost"
      GITEA__server__DISABLE_SSH: "true"
      GITEA__server__OFFLINE_MODE: "true"
      GITEA__security__INSTALL_LOCK: "true"
      GITEA__service__DISABLE_REGISTRATION: "true"
      GITEA__service__REQUIRE_SIGNIN_VIEW: "true"
      GITEA__repository__FORCE_PRIVATE: "true"
      GITEA__actions__ENABLED: "false"
      GITEA__database__DB_TYPE: "sqlite3"
    ports:
      - "127.0.0.1:3030:3000"
    volumes:
      - ./data:/var/lib/gitea
      - ./config:/etc/gitea
    security_opt:
      - no-new-privileges:true
    pids_limit: 512
    mem_limit: 2g
COMPOSE
chmod 0600 "$base/compose.yaml"
docker compose --project-name kmj-devforge -f "$base/compose.yaml" config -q || die COMPOSE_INVALID

cat > "$unit" <<UNIT
[Unit]
Description=KMJ DevForge fixed-action local host broker
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=root
Group=$(id -gn "$web_user")
Environment=DEVFORGE_WEB_USER=$web_user
RuntimeDirectory=kmj-devforge
RuntimeDirectoryMode=0750
ExecStart=/usr/bin/python3 /usr/local/libexec/kmj-devforge-broker.py
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
ReadWritePaths=/opt/kmj-devforge /var/lib/kmj-devforge /run/kmj-devforge
UMask=0077

[Install]
WantedBy=multi-user.target
UNIT
chmod 0644 "$unit"
systemctl daemon-reload
systemctl enable --now kmj-devforge-broker.service
systemctl is-active --quiet kmj-devforge-broker.service || die SERVICE_NOT_RUNNING
test -S /run/kmj-devforge/control.sock || die SOCKET_NOT_RUNNING

printf '%s\n' 'DEVFORGE_BOOTSTRAP=PASS' \
  "AUTHORIZED_WEB_USER=$web_user" \
  'NEXT=Login to KMJ Main Platform as verified Super Admin, open /operator/devforge, and click One-click setup.' \
  'GIT_UI=SSH tunnel localhost:3030 after installation' \
  "INITIAL_ADMIN_CREDENTIALS_ROOT_ONLY=$state/initial-admin-credentials.txt"
