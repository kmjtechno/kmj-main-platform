#!/usr/bin/env bash
set -Eeuo pipefail

DOMAIN="${KMJ_STAGE_DOMAIN:-staging.kmjtechno.com}"
SITE_USER="${KMJ_SITE_USER:-kmjstage}"
DEPLOY_BRANCH="${KMJ_DEPLOY_BRANCH:-staging-approved}"
REPO_DIR="/home/$SITE_USER/repos/kmj-main-platform"

pass=0
fail=0

ok(){ printf 'PASS  %s\n' "$1"; pass=$((pass+1)); }
bad(){ printf 'FAIL  %s\n' "$1"; fail=$((fail+1)); }

echo "KMJ TECHNO Main Platform - Server Verification"
echo

[[ "$(systemctl is-active nginx || true)" == "active" ]] && ok "CloudPanel/nginx active" || bad "CloudPanel/nginx"
[[ "$(systemctl is-active postgresql || true)" == "active" ]] && ok "PostgreSQL active" || bad "PostgreSQL"
command -v php8.5 >/dev/null && ok "PHP 8.5 present" || bad "PHP 8.5"
php8.5 -m 2>/dev/null | grep -qx pdo_pgsql && ok "PHP pdo_pgsql present" || bad "PHP pdo_pgsql"
id "$SITE_USER" >/dev/null 2>&1 && ok "staging user present" || bad "staging user"

node_v="$(sudo -u "$SITE_USER" -H bash -lc 'export NVM_DIR="$HOME/.nvm"; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"; node -v 2>/dev/null || true')"
[[ "$node_v" == v22.* ]] && ok "Node 22 ($node_v)" || bad "Node 22 ($node_v)"

rust_v="$(sudo -u "$SITE_USER" -H bash -lc '[ -f "$HOME/.cargo/env" ] && . "$HOME/.cargo/env"; rustc --version 2>/dev/null || true')"
[[ "$rust_v" == rustc* ]] && ok "$rust_v" || bad "Rust"

[[ "$(systemctl is-enabled kmj-stage-deploy.timer 2>/dev/null || true)" == "enabled" ]] && ok "deploy timer enabled" || bad "deploy timer enabled"
[[ "$(systemctl is-active kmj-stage-deploy.timer 2>/dev/null || true)" == "active" ]] && ok "deploy timer active" || bad "deploy timer active"

source_branch="$(grep '^BRANCH=' "/home/$SITE_USER/bin/kmj-stage-deploy.sh" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"')"
[[ "$source_branch" == "$DEPLOY_BRANCH" ]] && ok "deploy source = $DEPLOY_BRANCH" || bad "deploy source ($source_branch)"

if [[ -d "$REPO_DIR/.git" ]]; then
  sudo -u "$SITE_USER" -H git -C "$REPO_DIR" fetch -q origin \
    "+refs/heads/$DEPLOY_BRANCH:refs/remotes/origin/$DEPLOY_BRANCH" || true
  remote="$(sudo -u "$SITE_USER" -H git -C "$REPO_DIR" rev-parse "origin/$DEPLOY_BRANCH" 2>/dev/null || true)"
  live="$(cat "/home/$SITE_USER/.kmj-stage-last-success" 2>/dev/null || true)"
  [[ -n "$remote" ]] && ok "approved remote resolves ($remote)" || bad "approved remote"
  [[ -n "$live" && "$live" == "$remote" ]] && ok "live commit matches approved remote" || bad "live=$live remote=$remote"
else
  bad "repository clone"
fi

http="$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "https://$DOMAIN" || true)"
case "$http" in
  2*|3*) ok "HTTPS status $http" ;;
  *) bad "HTTPS status $http" ;;
esac

robots="$(curl -s --max-time 15 "https://$DOMAIN/robots.txt" || true)"
grep -Fxq 'Disallow: /' <<<"$robots" && ok "staging no-index" || bad "staging no-index"

echo
echo "PASS=$pass FAIL=$fail"
[[ "$fail" -eq 0 ]]
