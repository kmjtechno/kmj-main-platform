#!/usr/bin/env bash
set -Eeuo pipefail
umask 027

# KMJ TECHNO Main Platform - Reproducible Staging Server Bootstrap
# Stable entrypoint. Safe to rerun. Do not fork this into V2/V3 files.
#
# Target:
#   Ubuntu 24.04 LTS amd64
#   CloudPanel + PHP 8.5
#   PostgreSQL 18 (local only)
#   Node.js 22 via NVM
#   Rust stable
#   GitHub read-only deploy identity
#   CI-gated staging-approved deployment
#   systemd continuous deployment
#
# Boundaries:
#   - staging only
#   - production kmjtechno.com untouched
#   - KMJ Cloud Nexus untouched
#   - no paid dependency required

VERSION="1.0.0"
DOMAIN="${KMJ_STAGE_DOMAIN:-staging.kmjtechno.com}"
SITE_USER="${KMJ_SITE_USER:-kmjstage}"
PANEL_USER="${KMJ_PANEL_USER:-kmjadmin}"
PANEL_EMAIL="${KMJ_PANEL_EMAIL:-admin@kmjtechno.com}"
DB_NAME="${KMJ_DB_NAME:-kmj_platform_staging}"
DB_USER="${KMJ_DB_USER:-kmj_platform}"
REPO_SSH="${KMJ_REPO_SSH:-git@github.com:kmjtechno/kmj-main-platform.git}"
DEPLOY_BRANCH="${KMJ_DEPLOY_BRANCH:-staging-approved}"
TIMEZONE="${KMJ_TIMEZONE:-Asia/Kolkata}"

CLOUDPANEL_INSTALLER_URL="https://installer.cloudpanel.io/ce/v2/install.sh"
CLOUDPANEL_SHA256_DEFAULT="8146dbe0a488e7088b04071b0c34d59aa0ab1fe9dcec382d395fd155c9e6c476"
CLOUDPANEL_SHA256="${KMJ_CLOUDPANEL_SHA256:-$CLOUDPANEL_SHA256_DEFAULT}"

LOG="/root/kmj-server-bootstrap.log"
SECRETS="/root/.kmj-server-secrets"
CREDS="/root/KMJ_SERVER_CREDENTIALS.txt"
STATE="/root/KMJ_SERVER_BOOTSTRAP_STATE"
NEXT="/root/KMJ_SERVER_NEXT_ACTIONS.txt"

exec > >(tee -a "$LOG") 2>&1

green(){ printf '\033[1;32m%s\033[0m\n' "$*"; }
yellow(){ printf '\033[1;33m%s\033[0m\n' "$*"; }
red(){ printf '\033[1;31m%s\033[0m\n' "$*"; }
phase(){ printf '\n\033[1;36m[%s] %s\033[0m\n' "$1" "$2"; }

trap 'red "Bootstrap failed at line $LINENO. Re-run the SAME script after fixing the reported cause. Log: $LOG"' ERR

[[ $EUID -eq 0 ]] || { red "Run as root."; exit 1; }

. /etc/os-release
[[ "${ID:-}" == "ubuntu" && "${VERSION_ID:-}" == "24.04" ]] || {
  red "Supported OS is Ubuntu 24.04 LTS only."
  exit 2
}

[[ "$(dpkg --print-architecture)" == "amd64" ]] || {
  red "This bootstrap currently targets amd64."
  exit 3
}

export DEBIAN_FRONTEND=noninteractive
timedatectl set-timezone "$TIMEZONE" || true

cat > "$STATE" <<EOF
version=$VERSION
started_at=$(date -Is)
domain=$DOMAIN
deploy_branch=$DEPLOY_BRANCH
status=RUNNING
EOF
chmod 600 "$STATE"

phase "1/12" "Base system and safety packages"
rm -f /etc/apt/sources.list.d/pgdg.list /etc/apt/sources.list.d/pgdg.sources

apt-get update
apt-get install -y \
  curl wget sudo ca-certificates gnupg gpg git unzip zip rsync jq acl openssl \
  build-essential pkg-config libssl-dev clang cmake fail2ban util-linux python3 \
  ufw postgresql-common

systemctl enable --now fail2ban || true

phase "2/12" "CloudPanel"

if ! command -v clpctl >/dev/null 2>&1; then
  tmp="$(mktemp)"
  curl -fsSL "$CLOUDPANEL_INSTALLER_URL" -o "$tmp"
  actual="$(sha256sum "$tmp" | awk '{print $1}')"
  if [[ "$actual" != "$CLOUDPANEL_SHA256" ]]; then
    red "CloudPanel installer checksum changed."
    red "Expected: $CLOUDPANEL_SHA256"
    red "Actual:   $actual"
    red "Verify the current checksum in CloudPanel official documentation, then rerun with:"
    red "KMJ_CLOUDPANEL_SHA256=<verified_sha256> bash $0"
    rm -f "$tmp"
    exit 20
  fi
  DB_ENGINE=MYSQL_8.4 bash "$tmp"
  rm -f "$tmp"
fi

command -v clpctl >/dev/null 2>&1 || { red "CloudPanel CLI missing after install."; exit 21; }
systemctl is-active --quiet nginx || { red "CloudPanel nginx is not active."; exit 22; }

phase "3/12" "PostgreSQL 18 repository and server"

install -d -m 0755 /usr/share/postgresql-common/pgdg
curl -fsSL \
  https://www.postgresql.org/media/keys/ACCC4CF8.asc \
  -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc

cat > /etc/apt/sources.list.d/pgdg.sources <<EOF
Types: deb
URIs: https://apt.postgresql.org/pub/repos/apt
Suites: ${VERSION_CODENAME}-pgdg
Architectures: amd64
Components: main
Signed-By: /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc
EOF

apt-get update
candidate="$(apt-cache policy postgresql-18 | awk '/Candidate:/{candidate=$2} END{print candidate}')"
[[ -n "$candidate" && "$candidate" != "(none)" ]] || {
  red "PostgreSQL 18 package candidate is unavailable."
  exit 30
}

apt-get install -y postgresql-18 postgresql-client-18 libpq-dev
systemctl enable --now postgresql

PSQL18="/usr/lib/postgresql/18/bin/psql"
CREATEDB18="/usr/lib/postgresql/18/bin/createdb"
[[ -x "$PSQL18" ]] || { red "PostgreSQL 18 psql missing."; exit 31; }

phase "4/12" "Persistent server-local secrets and staging database"

if [[ ! -f "$SECRETS" ]]; then
  cat > "$SECRETS" <<EOF
KMJ_DB_PASSWORD=$(openssl rand -hex 24)
KMJ_PANEL_PASSWORD=$(openssl rand -hex 20)
KMJ_PANEL_BASIC_PASSWORD=$(openssl rand -hex 18)
KMJ_SITE_PASSWORD=$(openssl rand -hex 20)
EOF
  chmod 600 "$SECRETS"
fi

# shellcheck disable=SC1090
source "$SECRETS"

if sudo -u postgres "$PSQL18" -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1; then
  sudo -u postgres "$PSQL18" -v ON_ERROR_STOP=1 \
    -c "ALTER ROLE $DB_USER WITH LOGIN PASSWORD '$KMJ_DB_PASSWORD';"
else
  sudo -u postgres "$PSQL18" -v ON_ERROR_STOP=1 \
    -c "CREATE ROLE $DB_USER LOGIN PASSWORD '$KMJ_DB_PASSWORD';"
fi

if ! sudo -u postgres "$PSQL18" -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1; then
  sudo -u postgres "$CREATEDB18" -O "$DB_USER" "$DB_NAME"
fi

PG_CONF="/etc/postgresql/18/main/postgresql.conf"
if grep -Eq '^[# ]*listen_addresses[ ]*=' "$PG_CONF"; then
  sed -ri "s/^[# ]*listen_addresses[ ]*=.*/listen_addresses = '127.0.0.1'/" "$PG_CONF"
else
  printf "\nlisten_addresses = '127.0.0.1'\n" >> "$PG_CONF"
fi
systemctl restart postgresql

phase "5/12" "PHP 8.5 runtime and PostgreSQL bridge"

apt-get install -y \
  php8.5-cli php8.5-fpm php8.5-common php8.5-pgsql php8.5-curl \
  php8.5-mbstring php8.5-xml php8.5-bcmath php8.5-zip php8.5-intl php8.5-gd

php8.5 -m | grep -qx 'pdo_pgsql' || { red "PHP pdo_pgsql extension is missing."; exit 40; }
systemctl restart php8.5-fpm.service

phase "6/12" "CloudPanel account and Laravel staging site"

if clpctl user:list 2>/dev/null | grep -qiE "(^|[[:space:]])${PANEL_USER}([[:space:]]|$)"; then
  green "CloudPanel admin already exists; keeping its password unchanged."
else
  clpctl user:add \
    --userName="$PANEL_USER" \
    --email="$PANEL_EMAIL" \
    --firstName="KMJ" \
    --lastName="Admin" \
    --password="$KMJ_PANEL_PASSWORD" \
    --role="admin" \
    --timezone="$TIMEZONE" \
    --status="1"
fi

if [[ ! -d "/home/$SITE_USER/htdocs/$DOMAIN" ]]; then
  clpctl site:add:php \
    --domainName="$DOMAIN" \
    --phpVersion="8.5" \
    --vhostTemplate='Laravel 13' \
    --siteUser="$SITE_USER" \
    --siteUserPassword="$KMJ_SITE_PASSWORD"
fi

id "$SITE_USER" >/dev/null

phase "7/12" "Node.js 22 and Rust"

sudo -u "$SITE_USER" -H bash -lc '
  set -Eeuo pipefail
  export NVM_DIR="$HOME/.nvm"
  if [[ ! -s "$NVM_DIR/nvm.sh" ]]; then
    curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.7/install.sh | bash
  fi
  . "$NVM_DIR/nvm.sh"
  nvm install 22
  nvm alias default 22
  nvm use 22 >/dev/null
  node -v
  npm -v
'

sudo -u "$SITE_USER" -H bash -lc '
  set -Eeuo pipefail
  if [[ ! -x "$HOME/.cargo/bin/rustc" ]]; then
    curl --proto "=https" --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal
  fi
  . "$HOME/.cargo/env"
  rustup default stable
  rustc --version
  cargo --version
'

phase "8/12" "GitHub read-only deployment identity"

sudo -u "$SITE_USER" -H bash -lc '
  set -Eeuo pipefail
  mkdir -p "$HOME/.ssh"
  chmod 700 "$HOME/.ssh"
  if [[ ! -f "$HOME/.ssh/id_ed25519" ]]; then
    ssh-keygen -q -t ed25519 -N "" -f "$HOME/.ssh/id_ed25519" -C "kmj-main-platform-staging"
  fi
  touch "$HOME/.ssh/known_hosts"
  if ! ssh-keygen -F github.com -f "$HOME/.ssh/known_hosts" >/dev/null 2>&1; then
    ssh-keyscan -H github.com >> "$HOME/.ssh/known_hosts" 2>/dev/null
  fi
  chmod 600 "$HOME/.ssh/known_hosts"
'

DEPLOY_KEY="$(cat "/home/$SITE_USER/.ssh/id_ed25519.pub")"

phase "9/12" "Install resumable CI-gated deployment worker"

mkdir -p "/home/$SITE_USER/bin" "/home/$SITE_USER/repos"
cat > "/home/$SITE_USER/.kmj-stage-env" <<EOF
KMJ_DB_HOST=127.0.0.1
KMJ_DB_PORT=5432
KMJ_DB_DATABASE=$DB_NAME
KMJ_DB_USERNAME=$DB_USER
KMJ_DB_PASSWORD=$KMJ_DB_PASSWORD
KMJ_APP_URL=https://$DOMAIN
EOF
chown "$SITE_USER:$SITE_USER" "/home/$SITE_USER/.kmj-stage-env"
chmod 600 "/home/$SITE_USER/.kmj-stage-env"

cat > "/home/$SITE_USER/bin/kmj-stage-deploy.sh" <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail

exec 9>"\$HOME/.kmj-stage-deploy.lock"
flock -n 9 || exit 0

REPO="$REPO_SSH"
BRANCH="$DEPLOY_BRANCH"
DOMAIN="$DOMAIN"
REPO_DIR="\$HOME/repos/kmj-main-platform"
APP="\$REPO_DIR/apps/platform"
SITE_ROOT="\$HOME/htdocs/\$DOMAIN"
LOG="\$HOME/kmj-stage-deploy.log"
SUCCESS_FILE="\$HOME/.kmj-stage-last-success"

exec >>"\$LOG" 2>&1
echo
echo "===== \$(date -Is) STAGING DEPLOY CHECK ====="

AUTH_OUT="\$(ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -T git@github.com 2>&1 || true)"
if ! grep -Eq "successfully authenticated|shell access is disabled" <<<"\$AUTH_OUT"; then
  echo "GitHub deploy key is not authorized yet. No deployment performed."
  exit 0
fi

if [[ ! -d "\$REPO_DIR/.git" ]]; then
  git clone --branch "\$BRANCH" --single-branch "\$REPO" "\$REPO_DIR"
else
  git -C "\$REPO_DIR" config --add remote.origin.fetch \
    "+refs/heads/\$BRANCH:refs/remotes/origin/\$BRANCH" 2>/dev/null || true
  git -C "\$REPO_DIR" fetch --prune origin \
    "+refs/heads/\$BRANCH:refs/remotes/origin/\$BRANCH"
  git -C "\$REPO_DIR" reset --hard "origin/\$BRANCH"
fi

TARGET_SHA="\$(git -C "\$REPO_DIR" rev-parse HEAD)"
LAST_SUCCESS="\$(cat "\$SUCCESS_FILE" 2>/dev/null || true)"

printf 'User-agent: *\nDisallow: /\n' > "\$APP/public/robots.txt"

if [[ "\$TARGET_SHA" == "\$LAST_SUCCESS" ]]; then
  echo "Already successfully deployed: \$TARGET_SHA"
  exit 0
fi

[[ -f "\$APP/artisan" ]] || { echo "Laravel app missing: \$APP"; exit 50; }
cd "\$APP"

export NVM_DIR="\$HOME/.nvm"
. "\$NVM_DIR/nvm.sh"
nvm use 22 >/dev/null

COMPOSER="\$(command -v composer || true)"
[[ -n "\$COMPOSER" ]] || { echo "Composer not found."; exit 51; }

COMPOSER_MEMORY_LIMIT=-1 php8.5 "\$COMPOSER" install \
  --no-interaction --prefer-dist --optimize-autoloader

if [[ -f package-lock.json ]]; then
  npm ci --no-audit --no-fund
else
  npm install --no-audit --no-fund
fi
npm run build

if [[ ! -f .env ]]; then
  cp .env.example .env
  php8.5 artisan key:generate --force
fi

set -a
. "\$HOME/.kmj-stage-env"
set +a

python3 - <<'PY'
from pathlib import Path
import os

p = Path(".env")
text = p.read_text()
values = {
    "APP_ENV": "staging",
    "APP_DEBUG": "false",
    "APP_URL": os.environ["KMJ_APP_URL"],
    "DB_CONNECTION": "pgsql",
    "DB_HOST": os.environ["KMJ_DB_HOST"],
    "DB_PORT": os.environ["KMJ_DB_PORT"],
    "DB_DATABASE": os.environ["KMJ_DB_DATABASE"],
    "DB_USERNAME": os.environ["KMJ_DB_USERNAME"],
    "DB_PASSWORD": os.environ["KMJ_DB_PASSWORD"],
}
out, seen = [], set()
for line in text.splitlines():
    if "=" in line and not line.lstrip().startswith("#"):
        key = line.split("=", 1)[0]
        if key in values:
            out.append(f"{key}={values[key]}")
            seen.add(key)
            continue
    out.append(line)
for key, value in values.items():
    if key not in seen:
        out.append(f"{key}={value}")
p.write_text("\n".join(out) + "\n")
PY

php8.5 artisan migrate --force
php8.5 artisan optimize:clear
php8.5 artisan config:cache
php8.5 artisan view:cache || true
php8.5 artisan about >/dev/null

if [[ ! -L "\$SITE_ROOT" ]] || [[ "\$(readlink -f "\$SITE_ROOT")" != "\$(readlink -f "\$APP")" ]]; then
  if [[ -e "\$SITE_ROOT" && ! -L "\$SITE_ROOT" ]]; then
    mv "\$SITE_ROOT" "\${SITE_ROOT}.bootstrap-\$(date +%Y%m%d%H%M%S)"
  else
    rm -f "\$SITE_ROOT"
  fi
  ln -s "\$APP" "\$SITE_ROOT"
fi

HTTP_CODE="\$(curl -sS -o /dev/null -w '%{http_code}' -H "Host: \$DOMAIN" http://127.0.0.1/ || true)"
case "\$HTTP_CODE" in
  2*|3*) ;;
  *) echo "Local HTTP proof failed: \$HTTP_CODE"; exit 52 ;;
esac

printf '%s\n' "\$TARGET_SHA" > "\$SUCCESS_FILE"
echo "DEPLOYED AND VERIFIED: \$TARGET_SHA"
EOF

chown "$SITE_USER:$SITE_USER" "/home/$SITE_USER/bin/kmj-stage-deploy.sh"
chmod 750 "/home/$SITE_USER/bin/kmj-stage-deploy.sh"

cat > /etc/systemd/system/kmj-stage-deploy.service <<EOF
[Unit]
Description=KMJ Main Platform staging deployment
After=network-online.target postgresql.service
Wants=network-online.target

[Service]
Type=oneshot
User=$SITE_USER
Group=$SITE_USER
ExecStart=/home/$SITE_USER/bin/kmj-stage-deploy.sh
EOF

cat > /etc/systemd/system/kmj-stage-deploy.timer <<'EOF'
[Unit]
Description=KMJ Main Platform CI-gated staging live-update check

[Timer]
OnBootSec=2min
OnUnitActiveSec=2min
AccuracySec=20s
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now kmj-stage-deploy.timer

phase "10/12" "Firewall and emergency swap"

ufw allow 22/tcp >/dev/null || true
ufw allow 80/tcp >/dev/null || true
ufw allow 443/tcp >/dev/null || true
ufw allow 443/udp >/dev/null || true
ufw allow 8443/tcp >/dev/null || true
ufw --force enable >/dev/null || true

if ! swapon --show | grep -q .; then
  fallocate -l 4G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

cat > /etc/sysctl.d/99-kmj-staging.conf <<'EOF'
vm.swappiness=10
vm.vfs_cache_pressure=50
EOF
sysctl --system >/dev/null

phase "11/12" "Credentials, pending actions and optional first deployment"

SERVER_IP="$(curl -4 -fsS --max-time 10 https://api.ipify.org 2>/dev/null || true)"

cat > "$CREDS" <<EOF
KMJ TECHNO - STAGING SERVER CREDENTIALS
Generated: $(date -Is)
Bootstrap version: $VERSION

CloudPanel URL: https://${SERVER_IP:-SERVER_IP}:8443
CloudPanel admin: $PANEL_USER
CloudPanel admin password: $KMJ_PANEL_PASSWORD

PostgreSQL:
Host: 127.0.0.1
Port: 5432
Database: $DB_NAME
Username: $DB_USER
Password: $KMJ_DB_PASSWORD

Staging:
Domain: $DOMAIN
Linux user: $SITE_USER
Deploy branch: $DEPLOY_BRANCH
EOF
chmod 600 "$CREDS"

GITHUB_READY=false
AUTH_OUT="$(sudo -u "$SITE_USER" -H ssh -o BatchMode=yes -T git@github.com 2>&1 || true)"
if grep -Eq "successfully authenticated|shell access is disabled" <<<"$AUTH_OUT"; then
  GITHUB_READY=true
  sudo -u "$SITE_USER" -H "/home/$SITE_USER/bin/kmj-stage-deploy.sh"
fi

DNS_READY=false
if [[ -n "$SERVER_IP" ]]; then
  RESOLVED="$(getent ahostsv4 "$DOMAIN" 2>/dev/null | awk 'NR==1{print $1}' || true)"
  if [[ "$RESOLVED" == "$SERVER_IP" ]]; then
    DNS_READY=true
    clpctl lets-encrypt:install:certificate --domainName="$DOMAIN" || true
  fi
fi

cat > "$NEXT" <<EOF
KMJ TECHNO - SERVER BOOTSTRAP NEXT ACTIONS

GitHub deploy key:
$DEPLOY_KEY

Repository:
kmjtechno/kmj-main-platform

Deploy key must be READ-ONLY.

DNS A record:
$DOMAIN -> ${SERVER_IP:-<this-server-public-ip>}

Current readiness:
GitHub deploy key authorized: $GITHUB_READY
DNS points to this server: $DNS_READY

After either pending account-level action is completed, re-run THE SAME:
  bash /root/KMJ_SERVER_BOOTSTRAP.sh

Do not create a V2/V3 copy. This bootstrap is intentionally idempotent and resumable.

SAFE TO SHARE:
$NEXT
$LOG

DO NOT SHARE:
$CREDS
$SECRETS
EOF
chmod 600 "$NEXT"

phase "12/12" "Final verification"

echo "Bootstrap version: $VERSION"
echo "Kernel: $(uname -r)"
echo "CloudPanel/nginx: $(systemctl is-active nginx)"
echo "PostgreSQL: $(systemctl is-active postgresql)"
echo "PostgreSQL version: $("$PSQL18" --version)"
echo "PHP: $(php8.5 -r 'echo PHP_VERSION;')"
echo "PHP pgsql: $(php8.5 -m | grep -E 'pdo_pgsql|pgsql' | paste -sd, -)"
echo "Node: $(sudo -u "$SITE_USER" -H bash -lc 'export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"; node -v')"
echo "Rust: $(sudo -u "$SITE_USER" -H bash -lc '. "$HOME/.cargo/env"; rustc --version')"
echo "Deploy branch: $DEPLOY_BRANCH"
echo "Deploy timer: $(systemctl is-active kmj-stage-deploy.timer)"
echo "Firewall: $(ufw status | head -1)"
echo "GitHub ready: $GITHUB_READY"
echo "DNS ready: $DNS_READY"

if [[ "$GITHUB_READY" == "true" && "$DNS_READY" == "true" ]]; then
  HTTP="$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "https://$DOMAIN" || true)"
  ROBOTS="$(curl -s --max-time 15 "https://$DOMAIN/robots.txt" || true)"
  echo "HTTPS status: $HTTP"
  echo "Robots: $(printf '%s' "$ROBOTS" | tr '\n' ' ')"
  cat > "$STATE" <<EOF
version=$VERSION
completed_at=$(date -Is)
domain=$DOMAIN
deploy_branch=$DEPLOY_BRANCH
status=READY
EOF
  green "KMJ SERVER BOOTSTRAP READY"
else
  cat > "$STATE" <<EOF
version=$VERSION
updated_at=$(date -Is)
domain=$DOMAIN
deploy_branch=$DEPLOY_BRANCH
status=ACCOUNT_ACTION_PENDING
github_ready=$GITHUB_READY
dns_ready=$DNS_READY
EOF
  yellow "Base server is ready. One or more account-level actions are pending."
  yellow "See: $NEXT"
  yellow "After completing them, re-run THIS SAME bootstrap file."
fi

yellow "Never paste $CREDS or $SECRETS into chat."
