#!/usr/bin/env bash
# READ-ONLY root diagnostic for a failed offsite backup systemd unit.
#
# Purpose: classify why kmj-elite-offsite-backup.service exited non-zero (for
# example 255, which scripts/backup_platform.sh itself can never return; 255 is
# the classic ssh/sftp failure code or a wrapper's generic failure).
#
# Guarantees: no service start/stop/restart, no file writes, no network, no
# arguments (fixed unit, no receipt path: the operator redirects stdout if a
# receipt is wanted). Output is data-minimised: unit state, owner/mode/sha256
# of the executable and env/ssh files, free space, and a CLASS NAME derived
# from the journal. Raw journal lines, executable contents and environment
# values are never printed, so redaction can never be the only protection.
set -Eeuo pipefail
umask 077
[[ $# -eq 0 ]] || { echo 'BLOCKED=NO_ARGUMENTS_ACCEPTED'; exit 2; }
unit='kmj-elite-offsite-backup.service'

[[ "$(id -u)" == 0 ]] || { echo 'BLOCKED=ROOT_REQUIRED_FOR_JOURNAL'; exit 2; }
show() { systemctl show "$unit" --property="$1" --value 2>/dev/null || true; }
kv() { printf '%s=%s\n' "$1" "$2"; }

kv generated_utc "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
kv unit "$unit"
kv load_state "$(show LoadState)"
kv active_state "$(show ActiveState)/$(show SubState)"
kv result "$(show Result)"
kv exec_main_status "$(show ExecMainStatus)"
kv exec_main_exit_timestamp "$(show ExecMainExitTimestamp)"
kv run_as_user "$(show User)"
kv working_directory "$(show WorkingDirectory)"

# ExecStart: report the executable path and integrity, never its arguments'
# values (they may embed remotes), and never the environment.
exec_path="$(show ExecStart | sed -nE 's/.*path=([^ ;]+).*/\1/p' | head -1)"
kv exec_path "${exec_path:-unknown}"
if [[ -n "$exec_path" && -f "$exec_path" ]]; then
  kv exec_owner_mode "$(stat -c '%U:%G %a' -- "$exec_path")"
  kv exec_sha256 "$(sha256sum -- "$exec_path" | cut -d' ' -f1)"
  kv exec_is_symlink "$([[ -L "$exec_path" ]] && echo yes || echo no)"
  kv exec_world_writable "$([[ -n "$(find "$exec_path" -maxdepth 0 -perm -0002 2>/dev/null)" ]] && echo YES_UNSAFE || echo no)"
else
  kv exec_present NO
fi

# EnvironmentFile(s): existence + owner/mode only.
while IFS= read -r envfile; do
  envfile="${envfile#-}"
  [[ -n "$envfile" ]] || continue
  if [[ -f "$envfile" ]]; then
    kv "envfile:$envfile" "present $(stat -c '%U:%G %a' -- "$envfile")"
  else
    kv "envfile:$envfile" MISSING
  fi
done < <(show EnvironmentFiles | tr ' ' '\n' | sed -E 's/\(ignore_errors=[a-z]+\)//')

# SSH material of the unit's user: names/modes only, never contents.
run_user="$(show User)"; run_user="${run_user:-root}"
home="$(getent passwd "$run_user" | cut -d: -f6 || true)"
if [[ -n "$home" && -d "$home/.ssh" ]]; then
  kv ssh_dir "$(stat -c '%U:%G %a' -- "$home/.ssh")"
  kv ssh_known_hosts "$([[ -s "$home/.ssh/known_hosts" ]] && echo present || echo MISSING_OR_EMPTY)"
  while IFS= read -r f; do
    kv "ssh_file:$(basename "$f")" "$(stat -c '%U:%G %a %s bytes' -- "$f")"
  done < <(find "$home/.ssh" -maxdepth 1 -type f ! -name 'known_hosts*' 2>/dev/null | sort)
else
  kv ssh_dir "none_for_user_${run_user}"
fi
command -v rclone >/dev/null 2>&1 && kv rclone "present" || kv rclone "absent"
command -v ssh >/dev/null 2>&1 && kv ssh "present" || kv ssh "absent"

kv disk_root_free_kib "$(df -Pk / | awk 'END{print $4}')"
kv disk_var_free_kib "$(df -Pk /var 2>/dev/null | awk 'END{print $4}')"
kv disk_var_free_inodes "$(df -Pi /var 2>/dev/null | awk 'END{print $4}')"

# Last invocation log, redacted, then classified by the first matching cause.
log="$(journalctl -u "$unit" -n 200 --no-pager -o cat 2>/dev/null || true)"
kv journal_lines_scanned "$(printf '%s' "$log" | grep -c '' || true)"

class=UNKNOWN_EXIT_255_NEEDS_LOG
match() { printf '%s\n' "$log" | grep -Eiq "$1"; }
if   match 'Permission denied \(publickey|Too many authentication failures|no mutual signature'; then class=SSH_AUTH_KEY_REJECTED
elif match 'Host key verification failed|REMOTE HOST IDENTIFICATION HAS CHANGED|No (ED25519|RSA|ECDSA) host key is known'; then class=SSH_HOSTKEY
elif match 'Connection (timed out|refused|reset)|No route to host|Network is unreachable|Could not resolve host|Temporary failure in name resolution'; then class=NETWORK_OR_REMOTE_DOWN
elif match 'No space left|Disk quota|storageQuotaExceeded|quota exceeded'; then class=DISK_OR_REMOTE_QUOTA
elif match 'oauth2|invalid_grant|token (has been )?(expired|revoked)|401|403'; then class=REMOTE_AUTH_TOKEN
elif match 'No such file or directory|command not found'; then class=MISSING_FILE_OR_TOOL
elif match 'Permission denied'; then class=LOCAL_PERMISSION
elif [[ -z "$log" ]]; then class=NO_JOURNAL_ENTRIES_ROTATED_OR_UNREADABLE
fi
kv failure_class "$class"
kv note_exit_255 "backup_platform.sh returns 2/3 or tool exit codes only; 255 means the wrapper or ssh/sftp stage failed"
kv raw_output_suppressed yes
kv recentBackupVerified_claim NO_THIS_SCRIPT_PROVES_NOTHING_ABOUT_BACKUP_VALIDITY
kv mutations NONE
