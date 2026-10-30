#!/usr/bin/env bash
# CI-only: runs the REAL pinned-SFTP push script against REAL OpenSSH sshd/sftp-server instances on
# 127.0.0.1 (non-production, throwaway user, throwaway keys). Never touches production data or hosts.
set -Eeuo pipefail
[[ "${GITHUB_ACTIONS:-}" == true && "${RUNNER_ENVIRONMENT:-}" == github-hosted && "${RUNNER_OS:-}" == Linux ]] || { echo 'BLOCKED: isolated GitHub-hosted Linux CI only'; exit 2; }
[[ "$(id -u)" == 0 ]] || { echo 'BLOCKED: run through sudo in CI'; exit 2; }
repo="$(cd "$(dirname "$0")/../.." && pwd)"
src="$repo/scripts/operations/push-offsite-pinned-sftp-20261030.sh"
# Release-neutral: any 40-hex candidate id; the object name is derived from its first 12 characters.
candidate=c0ffee123456$(od -An -N14 -tx1 /dev/urandom | tr -d '[:space:]')
[[ "$candidate" =~ ^[0-9a-f]{40}$ ]] || { echo 'BLOCKED: invalid candidate id'; exit 3; }
short=${candidate:0:12}
object="offsite-$short.tar.gz.age"
# Every run owns a new directory; never delete or reuse a fixed root path.
base="$(mktemp -d /var/lib/kmj-e2e.XXXXXXXX)"
chmod 0755 "$base"
test_user="kmje2e$(od -An -N4 -tx1 /dev/urandom | tr -d '[:space:]')"
[[ "$test_user" =~ ^kmje2e[0-9a-f]{8}$ ]] || { echo 'BLOCKED: invalid throwaway user'; exit 3; }
if getent passwd "$test_user" >/dev/null; then echo 'BLOCKED: user collision'; exit 3; fi
home="$base/home"
sftp_server=/usr/lib/openssh/sftp-server
[[ -x "$sftp_server" && -x /usr/sbin/sshd ]] || { echo 'BLOCKED: openssh-server missing'; exit 3; }
# No fixed-directory deletion, existing-account mutation, or shared home paths.
install -d -m 0755 -o root -g root "$base/backups"
[[ -d /run/sshd ]] || install -d -m 0755 -o root -g root /run/sshd
useradd -M -d "$home" -s /bin/bash -p '*' "$test_user"
install -d -m 0755 -o "$test_user" -g "$test_user" "$home" "$home/incoming" "$home/incoming2"
# GitHub-hosted runners are ephemeral: leave the isolated directory for runner teardown.
# Only delete the uniquely created account after verifying its recorded home.
cleanup() {
  for p in "$base"/sshd_*.pid; do
    [[ -f "$p" ]] && kill "$(cat "$p")" 2>/dev/null || true
  done
  if [[ "$(getent passwd "$test_user" | cut -d: -f6)" == "$home" ]]; then
    userdel "$test_user" || true
  fi
}
trap cleanup EXIT

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
AllowUsers $test_user
StrictModes no
Subsystem sftp $2
CONF
  /usr/sbin/sshd -f "$base/sshd_$1.conf" -E "$base/sshd_$1.log"
  for _ in $(seq 1 40); do ssh-keyscan -T 2 -t ed25519 -p "$1" 127.0.0.1 2>/dev/null | grep -q ssh-ed25519 && return 0; sleep 0.25; done
  echo "SSHD_$1=FAIL"; cat "$base/sshd_$1.log" || true; exit 1
}
start_sshd 2222 "$sftp_server"
start_sshd 2223 "$sftp_server -P hardlink"

# Rewrite only the three fixed root paths; nothing else in the production script changes.
sed -e "s#^CONF=.*#CONF=$base/offsite-sftp.conf#" \
    -e "s#^LOCAL=.*#LOCAL=$base/backups/$object#" \
    -e "s#^BACKUP_DIR=.*#BACKUP_DIR=$base/backups#" "$src" >"$base/push.sh"
chmod 0755 "$base/push.sh"
head -c 1048576 /dev/urandom >"$base/backups/$object"
chmod 0600 "$base/backups/$object"
local_sha="$(sha256sum "$base/backups/$object" | cut -d' ' -f1)"

conf() { # port remote_dir identity pin
  printf 'HOST=127.0.0.1\nPORT=%s\nUSER=%s\nREMOTE_DIR=%s\nIDENTITY_FILE=%s\nHOSTKEY_SHA256=%s\n' "$1" "$test_user" "$2" "$3" "$4" >"$base/offsite-sftp.conf"
  chmod 0600 "$base/offsite-sftp.conf"
}
out=''; rc=0
push() { set +e; out="$(bash "$base/push.sh" --candidate-sha "$candidate" 2>&1)"; rc=$?; set -e; echo "--- rc=$rc"; echo "$out"; }
expect() { grep -qF -- "$1" <<<"$out" || { echo "ASSERT_FAIL: missing '$1'"; exit 1; }; }
refuse() { ! grep -qF -- "$1" <<<"$out" || { echo "ASSERT_FAIL: unexpected '$1'"; exit 1; }; }
want_rc() { [[ "$rc" == "$1" ]] || { echo "ASSERT_FAIL: rc=$rc want $1"; exit 1; }; }
remote="$home/incoming/$object"
listing() { ls -A "$1" | tr '\n' ' '; }

echo '== 1 fresh upload, probe, hardlink commit, readback'
conf 2222 "$home/incoming" "$base/id" "$pin"; push
want_rc 0; expect REMOTE_CAPABILITY_PROBE=PASS; expect SFTP_UPLOAD=PASS; expect REMOTE_COMMIT_NO_CLOBBER=PASS
expect REMOTE_READBACK_SHA256=PASS; expect OFFSITE_PUSH=PASS; expect OFFSITE_RESTORE=NOT_VERIFIED
[[ "$(sha256sum "$remote" | cut -d' ' -f1)" == "$local_sha" ]] || { echo 'ASSERT_FAIL: remote digest'; exit 1; }
[[ "$(listing "$home/incoming")" == "$object " ]] || { echo "ASSERT_FAIL: leftovers: $(listing "$home/incoming")"; exit 1; }
[[ "$(stat -c %h "$remote")" == 1 ]] || { echo 'ASSERT_FAIL: final object still hardlinked to incoming'; exit 1; }

echo '== 2 rerun is idempotent (target exists, identical bytes)'
push; want_rc 0; expect REMOTE_COMMIT_NO_CLOBBER=TARGET_EXISTS_OR_FAILED; expect REMOTE_READBACK_SHA256=PASS
[[ "$(listing "$home/incoming")" == "$object " ]] || { echo 'ASSERT_FAIL: leftovers after rerun'; exit 1; }

echo '== 3 a different existing object is never replaced'
rm -f "$remote"; runuser -u "$test_user" -- sh -c 'printf OTHER > "$1"' sh "$remote"
push; want_rc 1; expect REMOTE_READBACK=DIGEST_MISMATCH; refuse OFFSITE_PUSH=PASS
[[ "$(cat "$remote")" == OTHER ]] || { echo 'ASSERT_FAIL: existing object was modified'; exit 1; }
[[ "$(listing "$home/incoming")" == "$object " ]] || { echo 'ASSERT_FAIL: leftovers after mismatch'; exit 1; }

echo '== 4 wrong host-key pin fails before any credential is offered'
conf 2222 "$home/incoming" "$base/id" "SHA256:$(printf 'A%.0s' $(seq 1 43))"; push
want_rc 1; expect HOSTKEY_PIN=MISMATCH; refuse REMOTE_CAPABILITY_PROBE

echo '== 5 rejected key is classified (the former exit 255 class)'
conf 2222 "$home/incoming" "$base/id_wrong" "$pin"; push
want_rc 1; expect REMOTE_CAPABILITY_PROBE=FAIL:SSH_AUTH_KEY_REJECTED; refuse SFTP_UPLOAD=PASS

echo '== 6 server without hardlink is refused before the large upload and leaves nothing behind'
conf 2223 "$home/incoming2" "$base/id" "$pin"; push
want_rc 1; expect REMOTE_CAPABILITY_PROBE=FAIL:REMOTE_HARDLINK_UNAVAILABLE; refuse SFTP_UPLOAD=PASS; refuse OFFSITE_PUSH=PASS
[[ -z "$(listing "$home/incoming2")" ]] || { echo "ASSERT_FAIL: left objects: $(listing "$home/incoming2")"; exit 1; }

echo 'OFFSITE_SFTP_REAL_SSHD_E2E=PASS'
echo 'PRODUCTION_HOST_CONTACTED=NO; PRODUCTION_BACKUP_USED=NO; OFFSITE_RESTORE=NOT_VERIFIED'
