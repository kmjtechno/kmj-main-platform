#!/usr/bin/env bash
# One-shot, root-only installer for the owner-key backup vault timer.
#
# Installs /usr/local/sbin/kmj-owner-key-backup-vault (from the already
# SHA-pinned script in /root/kmj-bootstrap), a hardened oneshot service and an
# hourly timer. The vault script is no-clobber and idempotent, so hourly runs
# only seal a snapshot that is not sealed yet. Deletes nothing. Rolls back its
# own unit files if systemd rejects them.
set -Eeuo pipefail
umask 022

SRC=/root/kmj-bootstrap/kmj-owner-key-backup-vault.sh
SRC_SHA=9b0b585999bebf2335da02ffbc2fdbf325e2defea849d1d9d908ac13033fe231
DST=/usr/local/sbin/kmj-owner-key-backup-vault
RCPT=/root/kmj-bootstrap/owner-age-recipient.txt
SVC=/etc/systemd/system/kmj-owner-key-vault.service
TMR=/etc/systemd/system/kmj-owner-key-vault.timer

die() { echo "OWNER_VAULT_TIMER=FAIL:$1" >&2; exit "${2:-1}"; }

[[ "$(id -u)" == 0 ]] || die ROOT_REQUIRED 2
command -v systemctl >/dev/null 2>&1 || die NO_SYSTEMD 2
[[ -f "$SRC" && ! -L "$SRC" ]] || die VAULT_SCRIPT_MISSING 3
[[ "$(sha256sum "$SRC" | cut -d' ' -f1)" == "$SRC_SHA" ]] || die VAULT_SCRIPT_SHA_MISMATCH 3
[[ -s "$RCPT" ]] || die RECIPIENT_FILE_MISSING 3

install -o root -g root -m 0750 "$SRC" "$DST"
[[ "$(sha256sum "$DST" | cut -d' ' -f1)" == "$SRC_SHA" ]] || die INSTALLED_SHA_MISMATCH 4

backup_dir=/root/.kmj-owner-vault-timer-backup
mkdir -p "$backup_dir"; chmod 700 "$backup_dir"
for f in "$SVC" "$TMR"; do
  if [[ -e "$f" ]]; then cp -p "$f" "$backup_dir/$(basename "$f").prev"; fi
done

cat > "$SVC" <<'UNIT'
[Unit]
Description=KMJ owner-key encrypted backup vault (newest verified daily snapshot)
After=local-fs.target

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/kmj-owner-key-backup-vault
User=root
UMask=0077
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=read-only
ReadOnlyPaths=/var/backups/kmj-elite-daily /root/kmj-bootstrap
ReadWritePaths=/var/backups/kmj-owner-vault
ProtectKernelTunables=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
LockPersonality=yes
TimeoutStartSec=30min
UNIT

cat > "$TMR" <<'UNIT'
[Unit]
Description=Hourly check: seal any new daily snapshot to the owner age key

[Timer]
OnCalendar=hourly
RandomizedDelaySec=300
Persistent=true

[Install]
WantedBy=timers.target
UNIT
chmod 644 "$SVC" "$TMR"

mkdir -p /var/backups/kmj-owner-vault; chmod 700 /var/backups/kmj-owner-vault

rollback() {
  for f in "$SVC" "$TMR"; do
    if [[ -e "$backup_dir/$(basename "$f").prev" ]]; then cp -p "$backup_dir/$(basename "$f").prev" "$f"; else rm -f "$f"; fi
  done
  systemctl daemon-reload || true
  echo "OWNER_VAULT_TIMER=ROLLED_BACK" >&2
}

if ! systemd-analyze verify "$SVC" "$TMR" >/dev/null 2>&1; then rollback; die UNIT_VERIFY_FAILED 5; fi
systemctl daemon-reload || { rollback; die DAEMON_RELOAD_FAILED 5; }
systemctl enable --now kmj-owner-key-vault.timer || { rollback; die TIMER_ENABLE_FAILED 5; }
systemctl start kmj-owner-key-vault.service || true
sleep 15

echo "OWNER_VAULT_TIMER=INSTALLED"
echo "TIMER_ENABLED=$(systemctl is-enabled kmj-owner-key-vault.timer)"
echo "TIMER_ACTIVE=$(systemctl is-active kmj-owner-key-vault.timer)"
systemctl show kmj-owner-key-vault.service -p Result -p ExecMainStatus
echo "NEXT_RUN=$(systemctl list-timers kmj-owner-key-vault.timer --no-legend | awk '{print $1,$2,$3}')"
echo "RESTORE_PROVEN=NO"
