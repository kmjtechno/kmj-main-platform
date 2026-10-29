#!/usr/bin/env bash
# Root-run, fixed-object, host-key-PINNED SFTP upload of the sealed encrypted
# offsite copy for candidate 39b88b36d071, with download-and-compare verify.
#
# Fixes the class of failure reported as "offsite exit 255 / AUTH": every ssh
# trust decision is explicit (pinned host-key fingerprint, one named identity,
# no agent, no fallback methods) and every failure is reported as a CLASS name,
# never as raw ssh/sftp output.
#
# Inputs (no arguments, no environment): the fixed root-owned config
#   /etc/kmj-codebridge/offsite-sftp.conf   (root:root, mode 0600)
# with KEY=VALUE lines: HOST PORT USER REMOTE_DIR IDENTITY_FILE HOSTKEY_SHA256
# This script never prints the config values, the identity, or remote output.
# It does not export, copy or print any private key, does not restart services,
# and never claims a restore: OFFSITE_RESTORE stays NOT_VERIFIED.
set -Eeuo pipefail
umask 077
CONF=/etc/kmj-codebridge/offsite-sftp.conf
LOCAL=/var/backups/kmj-platform/offsite-39b88b36d071.tar.gz.age
REMOTE_NAME=offsite-39b88b36d071.tar.gz.age
BACKUP_DIR=/var/backups/kmj-platform

status() { printf '%s=%s\n' "$1" "$2"; }
block() { status OFFSITE_PUSH "BLOCKED:$1"; exit 2; }

[[ $# -eq 0 ]] || block NO_ARGUMENTS_ACCEPTED
[[ "$(id -u)" == 0 ]] || block ROOT_REQUIRED
for tool in sftp ssh-keyscan ssh-keygen sha256sum stat mktemp flock; do
  command -v "$tool" >/dev/null 2>&1 || block "MISSING_$tool"
done

protected_file() { # path -> must be a root-owned, single-link, 0600 regular file
  local p=$1
  [[ -f "$p" && ! -L "$p" ]] || return 1
  [[ "$(stat -c '%u:%a:%h' -- "$p")" == "0:600:1" ]]
}
# Every parent directory must be root-owned and not group/world writable, so a
# non-root user can never swap a component of the path (symlink or rename).
protected_chain() {
  local p=$1 d meta
  d=$(dirname -- "$p")
  while :; do
    [[ -d "$d" && ! -L "$d" ]] || return 1
    meta=$(stat -c '%u:%a:%h' -- "$d") || return 1
    [[ "${meta%%:*}" == 0 ]] || return 1
    local mode=${meta#*:}; mode=${mode%%:*}
    (( (8#$mode & 8#022) == 0 )) || return 1
    [[ "$d" == / ]] && break
    d=$(dirname -- "$d")
  done
}
protected_chain "$CONF" || block CONFIG_PATH_CHAIN
protected_chain "$LOCAL" || block SEALED_OBJECT_PATH_CHAIN
protected_file "$CONF" || block CONFIG_NOT_ROOT_0600
protected_file "$LOCAL" || block SEALED_OBJECT_NOT_ROOT_0600

# Parse KEY=VALUE without sourcing (no code execution from config).
declare -A cfg=()
while IFS= read -r line || [[ -n "$line" ]]; do
  [[ -z "$line" || "$line" == \#* ]] && continue
  [[ "$line" =~ ^([A-Z0-9_]+)=([^[:space:]]*)$ ]] || block CONFIG_SYNTAX
  [[ -z "${cfg[${BASH_REMATCH[1]}]+x}" ]] || block CONFIG_DUPLICATE_KEY
  cfg[${BASH_REMATCH[1]}]=${BASH_REMATCH[2]}
done <"$CONF"
for key in HOST PORT USER REMOTE_DIR IDENTITY_FILE HOSTKEY_SHA256; do
  [[ -n "${cfg[$key]:-}" ]] || block "CONFIG_MISSING_$key"
done
[[ ${#cfg[@]} -eq 6 ]] || block CONFIG_UNKNOWN_KEY
host=${cfg[HOST]} port=${cfg[PORT]} user=${cfg[USER]}
rdir=${cfg[REMOTE_DIR]} ident=${cfg[IDENTITY_FILE]} pin=${cfg[HOSTKEY_SHA256]}
[[ "$host" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$ ]] || block CONFIG_HOST
[[ "$port" =~ ^[0-9]{1,5}$ && "$port" -ge 1 && "$port" -le 65535 ]] || block CONFIG_PORT
[[ "$user" =~ ^[a-z_][a-z0-9_-]{0,31}$ ]] || block CONFIG_USER
[[ "$rdir" =~ ^/[A-Za-z0-9._/-]{1,200}$ && "$rdir" != *..* && "$rdir" != */ ]] || block CONFIG_REMOTE_DIR
[[ "$pin" =~ ^SHA256:[A-Za-z0-9+/]{43}$ ]] || block CONFIG_HOSTKEY_PIN
[[ "$ident" == /* && "$ident" != *..* ]] || block CONFIG_IDENTITY_PATH
protected_chain "$ident" || block IDENTITY_PATH_CHAIN
protected_file "$ident" || block IDENTITY_NOT_ROOT_0600

protected_chain "$BACKUP_DIR/x" || block BACKUP_DIR_PATH_CHAIN
[[ "$(stat -c '%u' -- "$BACKUP_DIR")" == 0 ]] || block BACKUP_DIR_OWNER
exec 9<"$BACKUP_DIR"
flock -n 9 || block ALREADY_RUNNING

tmp=$(mktemp -d "$BACKUP_DIR/.kmj-offsite-push.XXXXXXXX")
chmod 700 "$tmp"
trap 'rm -rf -- "$tmp"' EXIT

# Classify (never print) tool stderr.
classify() {
  local f=$1
  if   grep -Eiq 'Permission denied \(publickey|Too many authentication failures|no mutual signature|Load key|invalid format|incorrect passphrase' "$f"; then echo SSH_AUTH_KEY_REJECTED
  elif grep -Eiq 'Host key verification failed|REMOTE HOST IDENTIFICATION HAS CHANGED' "$f"; then echo SSH_HOSTKEY
  elif grep -Eiq 'timed out|refused|No route|unreachable|Could not resolve|reset by peer|Connection closed' "$f"; then echo NETWORK_OR_REMOTE_DOWN
  elif grep -Eiq 'No space left|quota' "$f"; then echo REMOTE_QUOTA
  elif grep -Eiq 'No such file|not found' "$f"; then echo REMOTE_PATH_MISSING
  elif grep -Eiq 'Permission denied|Failure' "$f"; then echo REMOTE_PERMISSION
  else echo UNCLASSIFIED; fi
}

# 1) Pin the host key by fingerprint BEFORE any credential is offered.
if ! ssh-keyscan -T 15 -t ed25519 -p "$port" -- "$host" >"$tmp/scan" 2>"$tmp/scan.err" || [[ ! -s "$tmp/scan" ]]; then
  status HOSTKEY_FETCH "FAIL:$(classify "$tmp/scan.err")"; status OFFSITE_PUSH FAIL; exit 1
fi
fp=$(ssh-keygen -lf "$tmp/scan" -E sha256 2>/dev/null | awk 'NR==1{print $2}')
[[ "$fp" == "$pin" ]] || { status HOSTKEY_PIN MISMATCH; status OFFSITE_PUSH FAIL; exit 1; }
status HOSTKEY_PIN PASS
printf '[%s]:%s %s\n' "$host" "$port" "$(awk 'NR==1{print $2" "$3}' "$tmp/scan")" >"$tmp/known_hosts"

sftp_opts=(-o LogLevel=ERROR -P "$port" -i "$ident"
  -o BatchMode=yes -o IdentitiesOnly=yes -o IdentityAgent=none
  -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$tmp/known_hosts" -o GlobalKnownHostsFile=/dev/null
  -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no -o PubkeyAuthentication=yes
  -o ForwardAgent=no -o ForwardX11=no -o ConnectTimeout=20 -o ServerAliveInterval=15 -o ServerAliveCountMax=3)

run_sftp() { # name, batch-file -> exit status; stderr kept for classification only
  sftp "${sftp_opts[@]}" -b "$2" -- "$user@$host" >/dev/null 2>"$tmp/$1.err"
}

local_sha=$(sha256sum -- "$LOCAL" | cut -d' ' -f1)
status LOCAL_ENCRYPTED_SHA256 "$local_sha"

# 2) Exclusive publication. Every run uploads to its OWN unique incoming name
# and commits with sftp `rename`, which OpenSSH implements WITHOUT overwrite
# (it fails if the target exists; `posix-rename` is deliberately never used).
# So two runs, or a stale .part, can never clobber the final object.
uniq=$(od -An -N10 -tx1 /dev/urandom | tr -d ' \n')
[[ "$uniq" =~ ^[0-9a-f]{20}$ ]] || block RANDOM_UNAVAILABLE
incoming="$rdir/.incoming-$REMOTE_NAME.$uniq"
final="$rdir/$REMOTE_NAME"

printf 'put %s %s\n' "$LOCAL" "$incoming" >"$tmp/b_put"
if ! run_sftp put "$tmp/b_put"; then
  printf -- '-rm %s\n' "$incoming" >"$tmp/b_cleanup"; run_sftp cleanup "$tmp/b_cleanup" || true
  status SFTP_UPLOAD "FAIL:$(classify "$tmp/put.err")"; status OFFSITE_PUSH FAIL; exit 1
fi
status SFTP_UPLOAD PASS

printf 'rename %s %s\n' "$incoming" "$final" >"$tmp/b_commit"
if run_sftp commit "$tmp/b_commit"; then
  status REMOTE_COMMIT_NO_CLOBBER PASS
else
  # Target exists (or commit failed). Only an identical existing object is
  # acceptable; it is verified byte-for-byte below, never assumed.
  status REMOTE_COMMIT_NO_CLOBBER TARGET_EXISTS_OR_FAILED
  printf -- '-rm %s\n' "$incoming" >"$tmp/b_cleanup"; run_sftp cleanup "$tmp/b_cleanup" || true
fi

# 4) Independent verification: download again and compare the digest.
printf 'get %s %s/verify\n' "$final" "$tmp" >"$tmp/b_verify"
if ! run_sftp verify "$tmp/b_verify" || [[ ! -f "$tmp/verify" ]]; then
  status REMOTE_READBACK "FAIL:$(classify "$tmp/verify.err")"; status OFFSITE_PUSH FAIL; exit 1
fi
if [[ "$(sha256sum -- "$tmp/verify" | cut -d' ' -f1)" != "$local_sha" ]]; then
  status REMOTE_READBACK DIGEST_MISMATCH; status OFFSITE_PUSH FAIL; exit 1
fi
status REMOTE_READBACK_SHA256 PASS
status OFFSITE_PUSH PASS
status OFFSITE_RESTORE NOT_VERIFIED
status PRODUCTION_CHANGED NO
