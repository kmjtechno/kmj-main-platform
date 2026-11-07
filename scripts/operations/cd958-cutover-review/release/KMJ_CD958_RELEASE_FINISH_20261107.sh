#!/bin/bash -p
# Reviewed operator steps to take cd958 live on KMJ-elite after the storage cutover and the
# isolated migration rehearsal PASS. Root only. Usage: bash -p <file> STEP
#
#   controller : upgrade the installed release controller 6d6d2788 (sha ae42b9f1) to merged
#                b192a2e5 (sha daa789f2) via a pinned patch; the old file is kept.
#   migrate    : run exactly the 4 additive cd958 migrations on production PostgreSQL
#                (create-table only; the running 574e code was proven compatible).
#   approve    : rewrite the protected approval to cd958 / expected current platform-574e443a2c75
#                after re-verifying controller, migrations and the backup witness.
#   activate   : start the existing guarded release unit (controller switches pointer, reloads
#                PHP-FPM, health-checks, auto-rolls back on failure), then verify and restart queue.
#   finish     : controller -> migrate -> approve -> activate, stopping at the first failure.
#   rollback   : EMERGENCY ONLY: pointer back to platform-574e443a2c75 (compatible with new schema).
#   status     : read-only summary.
set -Eeuo pipefail
umask 077
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
unset BASH_ENV ENV CDPATH
fail() { echo "KMJ_CD958_RELEASE=BLOCKED $1"; exit 2; }
mark() { printf '%s=%s\n' "$1" "$2"; }
[[ $- == *p* ]] || fail PRIVILEGED_BASH_REQUIRED
[[ "$#" -eq 1 ]] || fail ONE_STEP_REQUIRED
case "$1" in controller|migrate|approve|activate|finish|rollback|status) ;; *) fail UNKNOWN_STEP ;; esac
[[ "$(id -u)" == 0 && "$(hostname -s)" == KMJ-elite ]] || fail ROOT_ELITE_ONLY

readonly P=/srv/kmj-codebridge-projects/kmj-main-platform
readonly SHA=cd9580701d3cea19d7d4e4c96ebe70c0553fbf37
readonly SHORT=cd9580701d3c
readonly OLD_RELEASE=platform-574e443a2c75
readonly NEW_RELEASE="platform-$SHORT"
readonly ROOTDIR=/home/kmjprod
readonly CURRENT="$ROOTDIR/current"
readonly CAND="$ROOTDIR/releases/$NEW_RELEASE"
readonly CAPP="$CAND/apps/platform"
readonly LIB=/usr/local/libexec/kmj-codebridge
readonly CTL="$LIB/activate-main-platform-approved.py"
readonly CTL_OLD=ae42b9f18e4944c3cd1f6ba1feae8d1deb752832a642a2aa923346f2532e7a4a
readonly CTL_NEW=daa789f2fe9ddd3e39eb86b9dbc60416ecf3c9250cd7f77ba60222800750e56d
readonly PATCH_SRC="$P/scripts/KMJ_CD958_CONTROLLER_6D6D_TO_B192_20261107.patch"
readonly PATCH_SHA=fddf68837058c9d49db1c8489d196f6f4b351016352421a01a43739133c8f98b
readonly APPROVAL=/etc/kmj-codebridge/main-platform-production-release.json
readonly UNIT=kmj-main-platform-production-release.service
readonly QUEUE=kmj-main-platform-queue.service
readonly LOCK=/run/lock/kmj-main-platform-production-release.lock
readonly WITNESS="/var/backups/kmj-platform/pre-deploy-$SHORT.json"
readonly BACKUP="/var/backups/kmj-platform/pre-deploy-$SHORT.tar.gz"
readonly STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

sha() { sha256sum -- "$1" | cut -c1-64; }
pointer() { basename -- "$(readlink -f -- "$CURRENT")"; }
as_app() { runuser -u kmjprod -- env -i PATH=/usr/bin:/bin HOME=/nonexistent LC_ALL=C "$@"; }
hold_lock() {
  exec 9<"$LOCK"
  [[ "$(stat -Lc '%u:%h:%a' -- /proc/self/fd/9)" == "0:1:600" ]] || fail RELEASE_LOCK_UNSAFE
  flock -n 9 || fail RELEASE_OPERATION_BUSY
}
drop_lock() { exec 9<&-; }
# kmjprod must traverse WORK to read state.php; /root is 0700, so use a fresh private dir in /tmp
# (mktemp: unique, created 0700; then root:kmjprod 0750, never writable by kmjprod).
WORK="$(mktemp -d /tmp/kmj-cd958-release.XXXXXX)"
chmod 0750 "$WORK"; chown root:kmjprod "$WORK"
trap 'rm -rf -- "$WORK"' EXIT

# Production-environment migration state check. Runs as kmjprod in the candidate with its real
# (materialized, byte-identical) production .env. Prints only fixed markers and migration names.
cat >"$WORK/state.php" <<'PHP'
<?php
try {
    $phase = $argv[1] ?? '';
    $root = $argv[2] ?? '';
    require $root.'/vendor/autoload.php';
    $app = require $root.'/bootstrap/app.php';
    $app->make(\Illuminate\Contracts\Console\Kernel::class)->bootstrap();
    if (!$app->isProduction() || $app->configurationIsCached()) {
        throw new RuntimeException('PRODUCTION_UNCACHED_CONFIG_REQUIRED');
    }
    if (config('database.default') !== 'pgsql') {
        throw new RuntimeException('PRODUCTION_PGSQL_REQUIRED');
    }
    $expected = [
        '2026_10_29_120000_create_codebridge_workspace_tables',
        '2026_10_30_000000_create_omnidesk_renewal_challenges',
        '2026_10_30_120000_create_codebridge_workspace_jobs',
        '2026_10_31_120000_create_codebridge_workspace_tool_proposals',
    ];
    $tables = ['codebridge_workspace_conversations', 'codebridge_workspace_messages',
        'codebridge_workspace_events', 'omnidesk_renewal_challenges', 'codebridge_workspace_jobs',
        'codebridge_workspace_job_events', 'codebridge_workspace_tool_proposals'];
    $ran = \Illuminate\Support\Facades\DB::table('migrations')->pluck('migration')->all();
    $all = array_map(fn($p) => basename($p, '.php'), glob($root.'/database/migrations/*.php'));
    $pending = array_values(array_diff($all, $ran));
    sort($pending);
    $present = array_values(array_filter($tables, fn($t) => \Illuminate\Support\Facades\Schema::hasTable($t)));
    if ($pending === $expected && $present === []) {
        $state = 'PENDING_EXACT_FOUR';
    } elseif ($pending === [] && $present === $tables) {
        $state = 'APPLIED';
    } else {
        echo "PRODUCTION_PENDING=".implode(',', array_map(fn($m) => preg_replace('/[^A-Za-z0-9_]/', '', $m), $pending))."\n";
        echo "PRODUCTION_NEW_TABLES_PRESENT=".count($present)."\n";
        throw new RuntimeException('PRODUCTION_MIGRATION_STATE_UNEXPECTED');
    }
    if ($phase === 'after' && $state !== 'APPLIED') {
        throw new RuntimeException('PRODUCTION_MIGRATIONS_NOT_APPLIED');
    }
    echo "PRODUCTION_MIGRATION_STATE=".$state."\n";
} catch (Throwable $e) {
    $reason = preg_match('/\A[A-Z_]{3,80}\z/', $e->getMessage()) === 1 ? $e->getMessage() : 'RUNTIME_FAILURE';
    echo "PRODUCTION_MIGRATION_CHECK=FAIL_".$reason."\n";
    exit(2);
}
PHP
chown root:kmjprod "$WORK/state.php"; chmod 0640 "$WORK/state.php"
migration_state() { ( cd "$CAPP" && as_app php8.4 "$WORK/state.php" "$1" "$CAPP" ); }

verify_witness() {
  python3 -I - "$BACKUP" "$WITNESS" "$SHA" "$OLD_RELEASE" <<'PY'
import hashlib, json, os, re, stat, sys
archive, witness, sha, release = sys.argv[1:]
for path in (archive, witness):
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1 or info.st_mode & 0o022:
        raise SystemExit("BACKUP_WITNESS=UNSAFE")
data = json.load(open(witness, encoding="utf-8"))
if (not isinstance(data, dict) or set(data) != {"approvedSha", "currentRelease", "backupSha256"}
        or data["approvedSha"] != sha or data["currentRelease"] != release
        or not re.fullmatch(r"[a-f0-9]{64}", str(data["backupSha256"]))):
    raise SystemExit("BACKUP_WITNESS=MISMATCH")
h = hashlib.sha256()
with open(archive, "rb") as source:
    for chunk in iter(lambda: source.read(1 << 20), b""):
        h.update(chunk)
if h.hexdigest() != data["backupSha256"]:
    raise SystemExit("BACKUP_WITNESS=CHECKSUM_MISMATCH")
print("BACKUP_WITNESS=PASS")
PY
}

step_controller() {
  [[ -f "$CTL" && ! -L "$CTL" && "$(stat -c '%u:%h' -- "$CTL")" == "0:1" ]] || fail CONTROLLER_FILE_UNSAFE
  systemctl show -p ExecStart "$UNIT" | grep -qF "path=$CTL ;" || fail RELEASE_UNIT_NOT_THIS_CONTROLLER
  local h; h="$(sha "$CTL")"
  if [[ "$h" == "$CTL_NEW" ]]; then mark CONTROLLER ALREADY_B192A2E5; return 0; fi
  [[ "$h" == "$CTL_OLD" ]] || fail "CONTROLLER_UNEXPECTED_HASH_$h"
  install -m 0400 -o root -g root -- "$PATCH_SRC" "$WORK/controller.patch"
  [[ "$(sha "$WORK/controller.patch")" == "$PATCH_SHA" ]] || fail CONTROLLER_PATCH_HASH_MISMATCH
  install -m 0400 -o root -g root -- "$CTL" "$WORK/old.py"
  patch --no-backup-if-mismatch -s -o "$WORK/new.py" "$WORK/old.py" "$WORK/controller.patch" || fail CONTROLLER_PATCH_FAILED
  [[ "$(sha "$WORK/new.py")" == "$CTL_NEW" ]] || fail CONTROLLER_RESULT_HASH_MISMATCH
  python3 -I -c 'import ast,sys; ast.parse(open(sys.argv[1], encoding="utf-8").read())' "$WORK/new.py" || fail CONTROLLER_PARSE_FAILED
  hold_lock  # never swap the controller while a release operation holds the lock
  install -m 0400 -o root -g root -- "$CTL" "$LIB/activate-main-platform-approved.py.6d6d2788-$STAMP"
  install -m 0750 -o root -g root -- "$WORK/new.py" "$LIB/.activate-main-platform-approved.py.$STAMP"
  mv -f -T -- "$LIB/.activate-main-platform-approved.py.$STAMP" "$CTL"
  drop_lock
  [[ "$(sha "$CTL")" == "$CTL_NEW" && "$(stat -c '%u:%g:%a:%h' -- "$CTL")" == "0:0:750:1" ]] || fail CONTROLLER_INSTALL_NOT_VERIFIED
  mark CONTROLLER UPGRADED_6D6D2788_TO_B192A2E5
  mark CONTROLLER_PREVIOUS_KEPT "$LIB/activate-main-platform-approved.py.6d6d2788-$STAMP"
}

step_migrate() {
  hold_lock
  [[ "$(pointer)" == "$OLD_RELEASE" ]] || fail LIVE_RELEASE_CHANGED
  [[ -s "$CAPP/.env" && ! -L "$CAPP/.env" && ! -e "$CAPP/bootstrap/cache/config.php" ]] || fail CANDIDATE_RUNTIME_NOT_READY
  [[ "$(as_app git -C "$CAND" rev-parse HEAD)" == "$SHA" ]] || fail CANDIDATE_WRONG_SHA
  local out; out="$(migration_state before)" || { echo "$out"; fail PRODUCTION_PRECHECK_FAILED; }
  echo "$out"
  if [[ "$out" == *"PRODUCTION_MIGRATION_STATE=APPLIED"* ]]; then
    mark PRODUCTION_MIGRATIONS ALREADY_APPLIED; drop_lock; return 0
  fi
  [[ "$out" == *"PRODUCTION_MIGRATION_STATE=PENDING_EXACT_FOUR"* ]] || fail PRODUCTION_PRECHECK_UNEXPECTED
  ( cd "$CAPP" && as_app php8.4 artisan migrate --force --no-interaction --no-ansi ) >"$WORK/migrate.log" 2>&1 \
    || { grep -oE 'SQLSTATE\[[A-Z0-9]{5}\]' "$WORK/migrate.log" | tail -1 | sed 's/^/PRODUCTION_MIGRATE_SQLSTATE=/' || :; fail PRODUCTION_MIGRATE_FAILED; }
  grep -oE '20[0-9]{2}_[0-9]{2}_[0-9]{2}_[0-9]{6}_[a-z0-9_]+' "$WORK/migrate.log" | sort -u | sed 's/^/PRODUCTION_MIGRATED=/' || :
  out="$(migration_state after)" || { echo "$out"; fail PRODUCTION_POSTCHECK_FAILED; }
  echo "$out"
  [[ "$(pointer)" == "$OLD_RELEASE" ]] || fail LIVE_RELEASE_CHANGED
  drop_lock
  mark PRODUCTION_MIGRATIONS APPLIED_EXACT_FOUR
}

step_approve() {
  [[ "$(sha "$CTL")" == "$CTL_NEW" ]] || fail CONTROLLER_NOT_UPGRADED_RUN_CONTROLLER
  hold_lock
  [[ "$(pointer)" == "$OLD_RELEASE" ]] || fail LIVE_RELEASE_CHANGED
  local out; out="$(migration_state after)" || { echo "$out"; fail PRODUCTION_MIGRATIONS_NOT_APPLIED_RUN_MIGRATE; }
  echo "$out"
  verify_witness || fail BACKUP_WITNESS_NOT_VERIFIED
  [[ -f "$APPROVAL" && ! -L "$APPROVAL" && "$(stat -c '%u:%h' -- "$APPROVAL")" == "0:1" ]] || fail APPROVAL_FILE_UNSAFE
  python3 -I - "$APPROVAL" "$SHA" "$OLD_RELEASE" "$STAMP" <<'PY'
import json, os, stat, sys
path, sha, current, stamp = sys.argv[1:]
directory = os.path.dirname(path)
info = os.lstat(path)
mode = stat.S_IMODE(info.st_mode) & 0o644
old = open(path, "rb").read()
keep = os.open(path + ".prev-" + stamp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
os.write(keep, old); os.fsync(keep); os.close(keep)
body = (json.dumps({"approvedSha": sha, "expectedCurrentRelease": current,
                    "backupVerified": True, "rollbackVerified": True}, indent=2) + "\n").encode()
temporary = path + ".new-" + stamp
fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
try:
    os.write(fd, body); os.fchown(fd, 0, 0); os.fchmod(fd, mode); os.fsync(fd)
finally:
    os.close(fd)
os.replace(temporary, path)
dfd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY); os.fsync(dfd); os.close(dfd)
data = json.load(open(path, encoding="utf-8"))
assert data == {"approvedSha": sha, "expectedCurrentRelease": current, "backupVerified": True, "rollbackVerified": True}
print("APPROVAL=WRITTEN_CD958_FROM_" + current)
print("APPROVAL_PREVIOUS_KEPT=" + path + ".prev-" + stamp)
PY
  drop_lock
}

health() {
  local code asset
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 --resolve kmjtechno.com:443:127.0.0.1 https://kmjtechno.com/login || :)"
  asset="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 --resolve kmjtechno.com:443:127.0.0.1 https://kmjtechno.com/assets/kmj-codebridge-icon.png || :)"
  mark HEALTH_LOGIN_HTTP "$code"; mark HEALTH_ASSET_HTTP "$asset"
  [[ "$code" == 200 && "$asset" == 200 ]]
}

restart_queue() {
  local before after i
  before="$(systemctl show -p MainPID --value "$QUEUE")"
  ( cd "$CURRENT/apps/platform" && as_app php8.4 artisan queue:restart --no-interaction --no-ansi ) >/dev/null 2>&1 \
    || { mark QUEUE_RESTART_SIGNAL FAILED; return 0; }
  for i in $(seq 1 60); do
    after="$(systemctl show -p MainPID --value "$QUEUE")"
    [[ "$after" != 0 && "$after" != "$before" ]] && break
    sleep 2
  done
  mark QUEUE_MAINPID_BEFORE "$before"; mark QUEUE_MAINPID_AFTER "$after"
  if [[ "$after" != 0 && -e "/proc/$after/cwd" ]]; then
    mark QUEUE_RUNTIME_RELEASE "$(readlink -f "/proc/$after/cwd" | sed -n 's#^/home/kmjprod/releases/\(platform-[a-f0-9]\{12\}\)/.*#\1#p')"
  fi
  mark QUEUE_UNIT_WORKDIR "$(systemctl show -p WorkingDirectory --value "$QUEUE")"
}

step_activate() {
  [[ "$(sha "$CTL")" == "$CTL_NEW" ]] || fail CONTROLLER_NOT_UPGRADED_RUN_CONTROLLER
  [[ "$(pointer)" == "$OLD_RELEASE" ]] || { [[ "$(pointer)" == "$NEW_RELEASE" ]] && { mark ACTIVATION ALREADY_ACTIVE; health || :; return 0; }; fail LIVE_RELEASE_UNEXPECTED; }
  grep -q "\"approvedSha\": \"$SHA\"" "$APPROVAL" || fail APPROVAL_NOT_CD958_RUN_APPROVE
  local since rc
  since="$(date -u '+%Y-%m-%d %H:%M:%S')"
  set +e
  systemctl start "$UNIT"; rc=$?
  set -e
  journalctl -u "$UNIT" --since "$since UTC" -o cat --no-pager 2>/dev/null | grep -E '^MAIN_PLATFORM_' | tail -10 || :
  mark RELEASE_UNIT_RC "$rc"
  mark POINTER "$(pointer)"
  if [[ "$rc" != 0 || "$(pointer)" != "$NEW_RELEASE" ]]; then
    health || :
    fail ACTIVATION_DID_NOT_COMPLETE_SEE_MARKERS
  fi
  mark DEPLOYED_GIT_HEAD "$(as_app git -C "$CAND" rev-parse HEAD)"
  health || fail POST_ACTIVATION_HEALTH_FAILED_CONSIDER_ROLLBACK
  restart_queue
  mark ACTIVATION PASS_CD958_LIVE
}

step_rollback() {
  hold_lock
  [[ "$(pointer)" == "$NEW_RELEASE" ]] || fail ROLLBACK_ONLY_FROM_CD958
  [[ -d "$ROOTDIR/releases/$OLD_RELEASE/apps/platform" && -L "$ROOTDIR/releases/$OLD_RELEASE/apps/platform/storage" ]] || fail OLD_RELEASE_NOT_READY
  ln -s "releases/$OLD_RELEASE" "$ROOTDIR/.current-rollback-$STAMP"
  mv -f -T -- "$ROOTDIR/.current-rollback-$STAMP" "$CURRENT"
  systemctl reload php8.4-fpm.service
  drop_lock
  mark POINTER "$(pointer)"
  health || :
  restart_queue
  mark ROLLBACK DONE_TO_574E
}

step_status() {
  mark POINTER "$(pointer)"
  mark CONTROLLER_SHA "$(sha "$CTL")"
  mark APPROVAL_FOR_CD958 "$(grep -q "\"approvedSha\": \"$SHA\"" "$APPROVAL" && echo yes || echo no)"
  migration_state after 2>/dev/null | grep -E '^PRODUCTION_' || :
  health || :
}

case "$1" in
  controller) step_controller ;;
  migrate) step_migrate ;;
  approve) step_approve ;;
  activate) step_activate ;;
  finish) step_controller; step_migrate; step_approve; step_activate ;;
  rollback) step_rollback ;;
  status) step_status ;;
esac
echo "KMJ_CD958_RELEASE_STEP=$1 DONE"
