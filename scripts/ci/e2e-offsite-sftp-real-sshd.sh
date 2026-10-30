#!/usr/bin/env bash
# CI-only: runs the REAL pinned-SFTP push script against REAL OpenSSH sshd/sftp-server instances on
# 127.0.0.1 (non-production, throwaway user, throwaway keys). Never touches production data or hosts.
set -Eeuo pipefail
[[ "${GITHUB_ACTIONS:-}" == true ]] || { echo 'BLOCKED: GitHub-hosted CI only'; exit 2; }
[[ "$(id -u)" == 0 ]] || { echo 'BLOCKED: run through sudo in CI'; exit 2; }
repo="$(cd "$(dirname "$0")/../.." && pwd)"
src="$repo/scripts/operations/push-offsite-39b88b36d071-pinned-sftp-20261029.sh"
base=/var/lib/kmj-e2e
sftp_server=/usr/lib/openssh/sftp-server
[[ -x "$sftp_server" && -x /usr/sbin/sshd ]] || { echo 'BLOCKED: openssh-server missing'; exit 3; }
# The push script demands a root-owned, non-group/world-writable path chain; show it for diagnosis.
namei -l "$base/x" 2>/dev/null || true
rm -rf "$base"; install -d -m 0755 -o root -g root "$base" "$base/backups"
mkdir -p /run/sshd
id kmjbackup >/dev/null 2>&1 || useradd -m -s /bin/bash kmjbackup
usermod -p '*' kmjbackup
install -d -m 0755 -o kmjbackup -g kmjbackup /home/kmjbackup/incoming /home/kmjbackup/incoming2
chmod 0755 /home/kmjbackup

ssh-keygen -q -t ed25519 -N '' -f "$base/hostkey"
ssh-keygen -q -t ed25519 -N '' -f "$base/id"
ssh-keygen -q -t ed25519 -N '' -f "$base/id_wrong"
chmod 0600 "$base/hostkey" "$base/id" "$base/id_wrong"
install -m 0644 -o root -g root "$base/id.pub" "$base/authorized_keys"
pin="$(ssh-keygen -lf "$base/hostkey.pub" -E sha256 | awk '{print $2}')"
[[ "$pin" =~ ^SHA256:[A-Za-z0-9+/]{43}$ ]]

start_sshd() { # port subsystem-command
  cat >"$base/sshd_$1.conf" <<CONF
Port $1
ListenAddress 127.0.0.1
HostKey $base/hostkey
PidFile $base/sshd_$1.pid
AuthorizedKeysFile $base/authorized_keys
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
UsePAM no
AllowUsers kmjbackup
StrictModes no
Subsystem sftp $2
CONF
  /usr/sbin/sshd -f "$base/sshd_$1.conf" -E "$base/sshd_$1.log"
  for _ in $(seq 1 40); do ssh-keyscan -T 2 -t ed25519 -p "$1" 127.0.0.1 2>/dev/null | grep -q ssh-ed25519 && return 0; sleep 0.25; done
  echo "SSHD_$1=FAIL"; cat "$base/sshd_$1.log" || true; exit 1
}
start_sshd 2222 "$sftp_server"
start_sshd 2223 "$sftp_server -P hardlink"
trap 'for p in "$base"/sshd_*.pid; do [[ -f "$p" ]] && kill "$(cat "$p")" 2>/dev/null || true; done' EXIT

# Rewrite only the three fixed root paths; nothing else in the production script changes.
sed -e "s#^CONF=.*#CONF=$base/offsite-sftp.conf#" \
    -e "s#^LOCAL=.*#LOCAL=$base/backups/offsite-39b88b36d071.tar.gz.age#" \
    -e "s#^BACKUP_DIR=.*#BACKUP_DIR=$base/backups#" "$src" >"$base/push.sh"
chmod 0755 "$base/push.sh"
head -c 1048576 /dev/urandom >"$base/backups/offsite-39b88b36d071.tar.gz.age"
chmod 0600 "$base/backups/offsite-39b88b36d071.tar.gz.age"
local_sha="$(sha256sum "$base/backups/offsite-39b88b36d071.tar.gz.age" | cut -d' ' -f1)"

conf() { # port remote_dir identity pin
  printf 'HOST=127.0.0.1\nPORT=%s\nUSER=kmjbackup\nREMOTE_DIR=%s\nIDENTITY_FILE=%s\nHOSTKEY_SHA256=%s\n' "$1" "$2" "$3" "$4" >"$base/offsite-sftp.conf"
  chmod 0600 "$base/offsite-sftp.conf"
}
out=''; rc=0
push() { set +e; out="$(bash "$base/push.sh" 2>&1)"; rc=$?; set -e; echo "--- rc=$rc"; echo "$out"; }
expect() { grep -qF -- "$1" <<<"$out" || { echo "ASSERT_FAIL: missing '$1'"; exit 1; }; }
refuse() { ! grep -qF -- "$1" <<<"$out" || { echo "ASSERT_FAIL: unexpected '$1'"; exit 1; }; }
want_rc() { [[ "$rc" == "$1" ]] || { echo "ASSERT_FAIL: rc=$rc want $1"; exit 1; }; }
remote=/home/kmjbackup/incoming/offsite-39b88b36d071.tar.gz.age
listing() { ls -A "$1" | tr '\n' ' '; }

echo '== 1 fresh upload, probe, hardlink commit, readback'
conf 2222 /home/kmjbackup/incoming "$base/id" "$pin"; push
want_rc 0; expect REMOTE_CAPABILITY_PROBE=PASS; expect SFTP_UPLOAD=PASS; expect REMOTE_COMMIT_NO_CLOBBER=PASS
expect REMOTE_READBACK_SHA256=PASS; expect OFFSITE_PUSH=PASS; expect OFFSITE_RESTORE=NOT_VERIFIED
[[ "$(sha256sum "$remote" | cut -d' ' -f1)" == "$local_sha" ]] || { echo 'ASSERT_FAIL: remote digest'; exit 1; }
[[ "$(listing /home/kmjbackup/incoming)" == 'offsite-39b88b36d071.tar.gz.age ' ]] || { echo "ASSERT_FAIL: leftovers: $(listing /home/kmjbackup/incoming)"; exit 1; }
[[ "$(stat -c %h "$remote")" == 1 ]] || { echo 'ASSERT_FAIL: final object still hardlinked to incoming'; exit 1; }

echo '== 2 rerun is idempotent (target exists, identical bytes)'
push; want_rc 0; expect REMOTE_COMMIT_NO_CLOBBER=TARGET_EXISTS_OR_FAILED; expect REMOTE_READBACK_SHA256=PASS
[[ "$(listing /home/kmjbackup/incoming)" == 'offsite-39b88b36d071.tar.gz.age ' ]] || { echo 'ASSERT_FAIL: leftovers after rerun'; exit 1; }

echo '== 3 a different existing object is never replaced'
rm -f "$remote"; sudo -u kmjbackup sh -c "printf OTHER > $remote"
push; want_rc 1; expect REMOTE_READBACK=DIGEST_MISMATCH; refuse OFFSITE_PUSH=PASS
[[ "$(cat "$remote")" == OTHER ]] || { echo 'ASSERT_FAIL: existing object was modified'; exit 1; }
[[ "$(listing /home/kmjbackup/incoming)" == 'offsite-39b88b36d071.tar.gz.age ' ]] || { echo 'ASSERT_FAIL: leftovers after mismatch'; exit 1; }

echo '== 4 wrong host-key pin fails before any credential is offered'
conf 2222 /home/kmjbackup/incoming "$base/id" "SHA256:$(printf 'A%.0s' $(seq 1 43))"; push
want_rc 1; expect HOSTKEY_PIN=MISMATCH; refuse REMOTE_CAPABILITY_PROBE

echo '== 5 rejected key is classified (the former exit 255 class)'
conf 2222 /home/kmjbackup/incoming "$base/id_wrong" "$pin"; push
want_rc 1; expect REMOTE_CAPABILITY_PROBE=FAIL:SSH_AUTH_KEY_REJECTED; refuse SFTP_UPLOAD=PASS

echo '== 6 server without hardlink is refused before the large upload and leaves nothing behind'
conf 2223 /home/kmjbackup/incoming2 "$base/id" "$pin"; push
want_rc 1; expect REMOTE_CAPABILITY_PROBE=FAIL:REMOTE_HARDLINK_UNAVAILABLE; refuse SFTP_UPLOAD=PASS; refuse OFFSITE_PUSH=PASS
[[ -z "$(listing /home/kmjbackup/incoming2)" ]] || { echo "ASSERT_FAIL: left objects: $(listing /home/kmjbackup/incoming2)"; exit 1; }

echo 'OFFSITE_SFTP_REAL_SSHD_E2E=PASS'
echo 'PRODUCTION_HOST_CONTACTED=NO; PRODUCTION_BACKUP_USED=NO; OFFSITE_RESTORE=NOT_VERIFIED'
