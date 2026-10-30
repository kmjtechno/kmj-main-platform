#!/usr/bin/env bash
# READ-ONLY root diagnostic for a failed offsite backup systemd unit.
#
# Purpose: classify why kmj-elite-offsite-backup.service exited non-zero (for
# example 255, which scripts/backup_platform.sh itself can never return; 255 is
# the classic ssh/sftp failure code or a wrapper's generic failure).
#
# Guarantees: no service start/stop/restart, no file writes, no network, no
# arguments (fixed unit, no receipt path: the operator redirects stdout if a
# receipt is wanted). Output contains only validated unit states, disk counts
# and a failure class derived from the journal. Raw journal lines, executable contents and environment
# values are never printed, so redaction can never be the only protection.
set -Eeuo pipefail
umask 077
[[ $# -eq 0 ]] || { echo 'BLOCKED=NO_ARGUMENTS_ACCEPTED'; exit 2; }
unit='kmj-elite-offsite-backup.service'

[[ "$(id -u)" == 0 ]] || { echo 'BLOCKED=ROOT_REQUIRED_FOR_JOURNAL'; exit 2; }
show() { systemctl show "$unit" --property="$1" --value 2>/dev/null || true; }
show_enum() {
  local value
  value="$(show "$1")"
  if [[ "$value" =~ ^[A-Za-z0-9_.-]{1,40}$ ]]; then
    printf '%s' "$value"
  else
    printf '%s' unknown
  fi
}
show_status() {
  local value
  value="$(show ExecMainStatus)"
  if [[ "$value" =~ ^[0-9]{1,3}$ ]]; then
    printf '%s' "$value"
  else
    printf '%s' unknown
  fi
}
kv() { printf '%s=%s\n' "$1" "$2"; }

kv generated_utc "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
kv unit "$unit"
kv load_state "$(show_enum LoadState)"
kv active_state "$(show_enum ActiveState)/$(show_enum SubState)"
kv result "$(show_enum Result)"
kv exec_main_status "$(show_status)"
# Never enumerate or print executable, working-directory, env-file, SSH key or user paths.
kv metadata_paths_exposed no

kv disk_root_free_kib "$(df -Pk / | awk 'END{print $4}')"
kv disk_var_free_kib "$(df -Pk /var 2>/dev/null | awk 'END{print $4}')"
kv disk_var_free_inodes "$(df -Pi /var 2>/dev/null | awk 'END{print $4}')"

# Classify only journal entries belonging to the exact failed systemd invocation.
# A unit-wide tail may include stale errors from previous attempts and is unsafe.
# Invalid/missing InvocationID, non-255 exit, or journal query failure => UNKNOWN.
invocation="$(show InvocationID)"
log=''
scope=UNAVAILABLE
if [[ "$(show_status)" == 255 && "$(show_enum Result)" == exit-code &&
      "$invocation" =~ ^[0-9a-fA-F]{32}$ ]]; then
  if log="$(journalctl --no-pager -o cat -n 200 "_SYSTEMD_INVOCATION_ID=$invocation" 2>/dev/null)"; then
    scope=EXACT_INVOCATION
  else
    log=''
  fi
fi
kv journal_scope "$scope"
kv journal_lines_scanned "$(printf '%s' "$log" | grep -c '' || true)"

class=UNKNOWN_EXIT_255_NEEDS_LOG
match() { printf '%s\n' "$log" | grep -Eiq "$1"; }
if [[ "$scope" == EXACT_INVOCATION && -n "$log" ]]; then
  if   match 'Permission denied \(publickey|Too many authentication failures|no mutual signature'; then class=SSH_AUTH_KEY_REJECTED
  elif match 'Host key verification failed|REMOTE HOST IDENTIFICATION HAS CHANGED|No (ED25519|RSA|ECDSA) host key is known'; then class=SSH_HOSTKEY
  elif match 'Connection (timed out|refused|reset)|No route to host|Network is unreachable|Could not resolve host|Temporary failure in name resolution'; then class=NETWORK_OR_REMOTE_DOWN
  elif match 'No space left|Disk quota|storageQuotaExceeded|quota exceeded'; then class=DISK_OR_REMOTE_QUOTA
  elif match 'oauth2|invalid_grant|token (has been )?(expired|revoked)|401|403'; then class=REMOTE_AUTH_TOKEN
  elif match 'No such file or directory|command not found'; then class=MISSING_FILE_OR_TOOL
  elif match 'Permission denied'; then class=LOCAL_PERMISSION
  fi
fi
kv failure_class "$class"
kv raw_output_suppressed yes
kv recentBackupVerified_claim NO_THIS_SCRIPT_PROVES_NOTHING_ABOUT_BACKUP_VALIDITY
kv mutations NONE
