#!/usr/bin/env bash
set -euo pipefail
umask 077

[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo 'Run as root/sudo.' >&2; exit 1; }

PROJECT_ID="${CODEBRIDGE_PROJECT_ID:-kmj-main-platform}"
INSTANCE="${CODEBRIDGE_INSTANCE:-kmj-main-platform}"
SERVICE_USER="${CODEBRIDGE_SERVICE_USER:-kmjrunner}"
SOURCE_ROOT="${CODEBRIDGE_SOURCE_ROOT:-}"
PROJECT_ROOT="${CODEBRIDGE_PROJECT_ROOT:-/srv/kmj-codebridge-projects/kmj-main-platform}"
RUNTIME="${CODEBRIDGE_RUNTIME:-/opt/kmj-codebridge-agent}"
NODE="${CODEBRIDGE_NODE:-}"
ENROLLMENT_BASE="${CODEBRIDGE_ENROLLMENT_BASE:-https://kmjtechno.com}"
STATE_DIR="${CODEBRIDGE_STATE_DIR:-/var/lib/kmj-codebridge-main-platform}"
CONFIG_DIR="${CODEBRIDGE_CONFIG_DIR:-/etc/kmj-codebridge/agents}"
CONFIG="$CONFIG_DIR/$INSTANCE.json"
SERVICE="kmj-codebridge-$INSTANCE.service"
SERVICE_FILE="/etc/systemd/system/$SERVICE"
SUPERVISOR_SOCKET="/run/kmj-codebridge/supervisor.sock"
ENROLLMENT_RESULT="/run/kmj-codebridge-$INSTANCE-enrollment-$$.json"

cleanup() { rm -f "$ENROLLMENT_RESULT"; }
trap cleanup EXIT

id "$SERVICE_USER" >/dev/null 2>&1 || { echo "Service user not found: $SERVICE_USER" >&2; exit 2; }
[[ -d "$RUNTIME" && -f "$RUNTIME/src/cli.js" && -f "$RUNTIME/scripts/enroll-device.js" ]] || {
  echo "CodeBridge runtime not found at $RUNTIME" >&2; exit 2;
}

if [[ -z "$NODE" ]]; then
  if [[ -x /opt/kmj-codebridge-node/bin/node ]]; then NODE=/opt/kmj-codebridge-node/bin/node; else NODE="$(command -v node || true)"; fi
fi
[[ -n "$NODE" && -x "$NODE" ]] || { echo 'Node.js runtime not found.' >&2; exit 2; }

if [[ -z "$SOURCE_ROOT" ]]; then
  if [[ -d /home/kmjprod/current/.git ]]; then SOURCE_ROOT=/home/kmjprod/current; else SOURCE_ROOT="$(pwd -P)"; fi
fi
SOURCE_ROOT="$(readlink -f "$SOURCE_ROOT")"
[[ -d "$SOURCE_ROOT/.git" ]] || { echo "Source checkout is not a Git repository: $SOURCE_ROOT" >&2; exit 2; }
[[ -f "$SOURCE_ROOT/apps/platform/composer.json" ]] || { echo 'Main Platform composer.json not found.' >&2; exit 2; }
grep -Fq '"name": "kmjtechno/kmj-main-platform"' "$SOURCE_ROOT/apps/platform/composer.json" || {
  echo 'Source checkout is not kmjtechno/kmj-main-platform.' >&2; exit 2;
}

install -d -m 0755 /srv/kmj-codebridge-projects
if [[ -e "$PROJECT_ROOT" ]]; then
  [[ -d "$PROJECT_ROOT/.git" ]] || { echo "Unsafe existing project path: $PROJECT_ROOT" >&2; exit 2; }
  grep -Fq '"name": "kmjtechno/kmj-main-platform"' "$PROJECT_ROOT/apps/platform/composer.json" || {
    echo 'Existing project root has wrong identity.' >&2; exit 2;
  }
else
  git clone --quiet --no-hardlinks "$SOURCE_ROOT" "$PROJECT_ROOT"
fi

git -C "$PROJECT_ROOT" remote set-url origin https://github.com/kmjtechno/kmj-main-platform.git || true
chown -R "$SERVICE_USER:$SERVICE_USER" "$PROJECT_ROOT"

install -d -m 0700 -o "$SERVICE_USER" -g "$SERVICE_USER" "$STATE_DIR" "$CONFIG_DIR"

if [[ -f "$CONFIG" ]]; then
  "$NODE" --input-type=module - "$CONFIG" "$PROJECT_ROOT" "$PROJECT_ID" <<'NODE'
import fs from 'node:fs';
const [file, root, projectId] = process.argv.slice(2);
const c = JSON.parse(fs.readFileSync(file, 'utf8'));
if (!Array.isArray(c.projects) || c.projects.length !== 1) process.exit(2);
if (c.projects[0].id !== projectId || fs.realpathSync(c.projects[0].root) !== fs.realpathSync(root)) process.exit(3);
NODE
  echo "Existing $PROJECT_ID agent config verified; no re-enrollment needed."
else
  DEVICE="${CODEBRIDGE_DEVICE_ID:-main-platform-$(hostname -s | tr -cd 'A-Za-z0-9_-' | cut -c1-40)}"
  echo 'Starting secure KMJ CodeBridge pairing for KMJ Main Platform.'
  "$NODE" "$RUNTIME/scripts/enroll-device.js"     "$ENROLLMENT_BASE" "$DEVICE" "$PROJECT_ID" "$PROJECT_ROOT" "$ENROLLMENT_RESULT"
  [[ -f "$ENROLLMENT_RESULT" ]] || { echo 'Enrollment did not produce a credential.' >&2; exit 3; }

  PROJECT_ROOT="$PROJECT_ROOT" PROJECT_ID="$PROJECT_ID" STATE_DIR="$STATE_DIR" CONFIG="$CONFIG"   ENROLLMENT_RESULT="$ENROLLMENT_RESULT" SUPERVISOR_SOCKET="$SUPERVISOR_SOCKET" "$NODE" --input-type=module <<'NODE'
import fs from 'node:fs';
const result = JSON.parse(fs.readFileSync(process.env.ENROLLMENT_RESULT, 'utf8'));
if (!result.agent || typeof result.agent.token !== 'string' || result.agent.token.length < 32) throw new Error('invalid enrollment result');
if (!Array.isArray(result.projects) || !result.projects.some(p => p.id === process.env.PROJECT_ID)) throw new Error('project not approved');
const perms = Array.isArray(result.permissions) ? result.permissions : [];
const root = fs.realpathSync(process.env.PROJECT_ROOT);
const script = root + '/scripts/codebridge-quality-gate.sh';
if (!fs.existsSync(script)) throw new Error('CodeBridge quality-gate script missing from Main Platform checkout');
const config = {
  gateway: result.gateway,
  token: result.agent.token,
  id: result.agent.id,
  tenant: result.agent.tenant,
  stateDir: process.env.STATE_DIR,
  supervisorSocket: process.env.SUPERVISOR_SOCKET,
  pollMs: 100,
  projects: [{
    id: process.env.PROJECT_ID,
    root,
    writable: perms.includes('write'),
    gates: {
      fast: { command: '/bin/bash', args: ['scripts/codebridge-quality-gate.sh', 'fast'], timeoutMs: 120000 },
      platform: { command: '/bin/bash', args: ['scripts/codebridge-quality-gate.sh', 'platform'], timeoutMs: 300000 },
      full: { command: '/bin/bash', args: ['scripts/codebridge-quality-gate.sh', 'full'], timeoutMs: 300000 }
    }
  }],
  license: { mode: 'free' }
};
const fd = fs.openSync(process.env.CONFIG, 'wx', 0o600);
try { fs.writeFileSync(fd, JSON.stringify(config, null, 2) + '\n'); fs.fsyncSync(fd); }
finally { fs.closeSync(fd); }
NODE
  chown "$SERVICE_USER:$SERVICE_USER" "$CONFIG"
fi

cat >"$SERVICE_FILE" <<EOF_UNIT
[Unit]
Description=KMJ CodeBridge Agent - Main Platform
After=network-online.target kmj-codebridge-supervisor.socket
Wants=network-online.target kmj-codebridge-supervisor.socket

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$RUNTIME
ExecStart=$NODE $RUNTIME/src/cli.js agent $CONFIG
Restart=always
RestartSec=2
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
LockPersonality=true
ReadWritePaths=$PROJECT_ROOT $STATE_DIR
UMask=0077

[Install]
WantedBy=multi-user.target
EOF_UNIT

systemctl daemon-reload
systemctl enable --now "$SERVICE"
systemctl is-active --quiet "$SERVICE"

echo "KMJ Main Platform CodeBridge project is active."
echo "project_id=$PROJECT_ID"
echo "project_root=$PROJECT_ROOT"
echo "service=$SERVICE"
