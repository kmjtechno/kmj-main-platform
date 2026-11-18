#!/bin/bash -p
# Owner-reviewed protected release for merged PR #873: Super Admin locked UI, exact main e5b43872 on KMJ-elite.
# Current live release: platform-e715829a56cc. GitHub e715 -> e5b comparison has no database migration files; live state must still be verified.
# Root only. Usage: bash -p <file> STEP
#
#   prepare     : pinned onepass (scripts/KMJ_B07_OWNER_ONEPASS_BUILD_BACKUP_OFFSITE_20261104.sh, sha 00706979):
#                 exact-main candidate build, real pg_dump + uploads backup with witness, disposable
#                 restore, age-encrypted Google SFTP copy with readback. No live change.
#   storage     : candidate-only storage switch to /home/kmjprod/shared/storage with the installed,
#                 pinned v6 scanner (the candidate serves no traffic; original kept frozen).
#   materialize : pinned materializer V2 (fd29c4eb): live .env byte copy, ACL and storage checks.
#   approve     : verify NO pending migration for the candidate against production, controller b192,
#                 backup witness; write the protected approval (previous kept).
#   activate    : existing guarded release unit, health, deployed HEAD, queue restart.
#   finish      : prepare -> storage -> materialize -> approve -> activate (stops at first failure).
#   rollback    : EMERGENCY ONLY: pointer back to platform-e715829a56cc.
#   status      : read-only summary.
set -Eeuo pipefail
umask 077
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
unset BASH_ENV ENV CDPATH
fail() { echo "KMJ_E5B438_RELEASE=BLOCKED $1"; exit 2; }
mark() { printf '%s=%s\n' "$1" "$2"; }
[[ $- == *p* ]] || fail PRIVILEGED_BASH_REQUIRED
[[ "$#" -eq 1 ]] || fail ONE_STEP_REQUIRED
case "$1" in prepare|storage|materialize|approve|activate|finish|rollback|status) ;; *) fail UNKNOWN_STEP ;; esac
[[ "$(id -u)" == 0 && "$(hostname -s)" == KMJ-elite ]] || fail ROOT_ELITE_ONLY

readonly P=/srv/kmj-codebridge-projects/kmj-main-platform
readonly SHA=e5b43872bc031eb4b074a1e318abd80949c321d8
readonly SHORT=e5b43872bc03
readonly OLD_RELEASE=platform-e715829a56cc
readonly PREVIOUS_SHA=e715829a56cc77e7aa63418ca1539635ae24e446
readonly NEW_RELEASE="platform-$SHORT"
readonly ROOTDIR=/home/kmjprod
readonly CURRENT="$ROOTDIR/current"
readonly CAND="$ROOTDIR/releases/$NEW_RELEASE"
readonly CAPP="$CAND/apps/platform"
readonly LIB=/usr/local/libexec/kmj-codebridge
readonly CTL="$LIB/activate-main-platform-approved.py"
readonly CTL_NEW=daa789f2fe9ddd3e39eb86b9dbc60416ecf3c9250cd7f77ba60222800750e56d
readonly ONEPASS_SRC="$P/scripts/KMJ_B07_OWNER_ONEPASS_BUILD_BACKUP_OFFSITE_20261104.sh"
readonly ONEPASS_SHA=0070697927babaa9a9035ebadcffe9a07311c12bcc4fbbd7a5a9d024cbc00dd3
readonly MATERIALIZER_SRC="$P/scripts/KMJ_CD958_CANDIDATE_RUNTIME_MATERIALIZE_V2_20261105.sh"
readonly MATERIALIZER_SHA=fd29c4ebcf224c45786f8cedd0e0d42bbfd414d706678fe820e0ead4eea3984f
readonly SCANNER=/usr/local/libexec/kmj-codebridge/main-platform-storage-switch-v6.py
readonly SCANNER_SHA=f4d01f6e3b40c9ad774c8ada5129b241cee93dac782ce75bb0e229b26bbc95ba
readonly SHARED=/home/kmjprod/shared/storage
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
WORK="$(mktemp -d /tmp/kmj-e5b438-release.XXXXXX)"
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
    $ran = \Illuminate\Support\Facades\DB::table('migrations')->pluck('migration')->all();
    $all = array_map(fn($p) => basename($p, '.php'), glob($root.'/database/migrations/*.php'));
    $pending = array_values(array_diff($all, $ran));
    sort($pending);
    if ($pending !== []) {
        echo "PRODUCTION_PENDING=".implode(',', array_map(fn($m) => preg_replace('/[^A-Za-z0-9_]/', '', $m), $pending))."\n";
        throw new RuntimeException('PRODUCTION_MIGRATION_PENDING_UNEXPECTED');
    }
    $state = 'NONE_PENDING';
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

step_prepare() {
  if [[ -d "$CAND/.git" && -f "$WITNESS" && -f "$BACKUP" ]]; then mark PREPARE ALREADY_STAGED_AND_BACKED_UP; return 0; fi
  [[ "$(pointer)" == "$OLD_RELEASE" ]] || fail LIVE_RELEASE_CHANGED
  install -m 0500 -o root -g root -- "$ONEPASS_SRC" "$WORK/onepass.sh"
  [[ "$(sha "$WORK/onepass.sh")" == "$ONEPASS_SHA" ]] || fail ONEPASS_HASH_MISMATCH
  bash "$WORK/onepass.sh" --candidate-sha "$SHA" --expected-release "$OLD_RELEASE" || fail PREPARE_FAILED
  [[ -d "$CAND/.git" && -f "$WITNESS" && -f "$BACKUP" ]] || fail PREPARE_OUTPUTS_MISSING
  [[ "$(as_app git -C "$CAND" rev-parse HEAD)" == "$SHA" ]] || fail CANDIDATE_WRONG_SHA
  mark PREPARE STAGED_BACKED_UP_OFFSITE
}

step_storage() {
  [[ -d "$CAPP" ]] || fail CANDIDATE_NOT_STAGED
  if [[ -L "$CAPP/storage" ]]; then
    [[ "$(readlink -f -- "$CAPP/storage")" == "$SHARED" ]] || fail CANDIDATE_STORAGE_LINK_UNEXPECTED
    mark CANDIDATE_STORAGE ALREADY_SHARED; return 0
  fi
  [[ "$(pointer)" == "$OLD_RELEASE" ]] || fail LIVE_RELEASE_CHANGED
  [[ "$(sha "$SCANNER")" == "$SCANNER_SHA" && "$(stat -c '%u' -- "$SCANNER")" == 0 ]] || fail SCANNER_PIN_MISMATCH
  install -m 0400 -o root -g root -- "$SCANNER" "$WORK/scanner.py"
  [[ "$(sha "$WORK/scanner.py")" == "$SCANNER_SHA" ]] || fail SCANNER_COPY_MISMATCH
  local plan id out
  plan="$(python3 -I -B "$WORK/scanner.py" plan --app-dir "$CAPP" --shared "$SHARED")" || { echo "$plan" | head -c 2000; fail CANDIDATE_PLAN_FAILED; }
  id="$(printf '%s' "$plan" | python3 -I -c 'import json,sys; v=json.load(sys.stdin); print(v["plan_id"] if v.get("ready") is True else "")')"
  [[ "$id" =~ ^[0-9a-f]{16}$ ]] || { echo "$plan" | head -c 2000; fail CANDIDATE_PLAN_NOT_READY; }
  out="$(python3 -I -B "$WORK/scanner.py" switch --apply --plan-id "$id" --app-dir "$CAPP" --shared "$SHARED")" \
    || { echo "$out" | head -c 2000; fail CANDIDATE_SWITCH_FAILED; }
  printf '%s' "$out" | python3 -I -c 'import json,sys; v=json.load(sys.stdin); sys.exit(0 if v.get("status")=="OK" else 2)' \
    || { echo "$out" | head -c 2000; fail CANDIDATE_SWITCH_NOT_OK; }
  [[ -L "$CAPP/storage" && "$(readlink -f -- "$CAPP/storage")" == "$SHARED" ]] || fail CANDIDATE_STORAGE_NOT_SHARED
  [[ "$(pointer)" == "$OLD_RELEASE" ]] || fail LIVE_RELEASE_CHANGED
  mark CANDIDATE_STORAGE SWITCHED_TO_SHARED
}

step_materialize() {
  if [[ -f "$CAPP/.env" && ! -L "$CAPP/.env" ]]; then mark MATERIALIZE ALREADY_DONE; return 0; fi
  install -m 0500 -o root -g root -- "$MATERIALIZER_SRC" "$WORK/materialize.sh"
  [[ "$(sha "$WORK/materialize.sh")" == "$MATERIALIZER_SHA" ]] || fail MATERIALIZER_HASH_MISMATCH
  local out
  out="$(bash -p "$WORK/materialize.sh" "$SHA" "$OLD_RELEASE" 2>&1)" || { echo "$out" | grep -E '^[A-Z_]+=' | tail -20; fail MATERIALIZE_FAILED; }
  echo "$out" | grep -E '^(KMJ_MATERIALIZE|KMJ_MATERIALIZE_SHARED|RUNTIME_ENV|NGINX_PUBLIC_ACL|NGINX_PRIVATE_ENV)=' || :
  grep -qx 'KMJ_MATERIALIZE=PASS' <<<"$out" || fail MATERIALIZE_NOT_PASS
  [[ "$(pointer)" == "$OLD_RELEASE" ]] || fail LIVE_RELEASE_CHANGED
}

verify_rollback_base() {
  local previous_app="$ROOTDIR/releases/$OLD_RELEASE/apps/platform"
  [[ -f "$previous_app/.env" && ! -L "$previous_app/.env" ]] || fail ROLLBACK_ENV_NOT_READY
  [[ -L "$previous_app/storage" && "$(readlink -f -- "$previous_app/storage")" == "$SHARED" ]] || fail ROLLBACK_STORAGE_NOT_SHARED
  [[ "$(as_app git -C "$ROOTDIR/releases/$OLD_RELEASE" rev-parse HEAD)" == "$PREVIOUS_SHA" ]] || fail ROLLBACK_BASE_SHA_DRIFT
  mark ROLLBACK_BASE_SHA VERIFIED
}
step_approve() {
  [[ "$(sha "$CTL")" == "$CTL_NEW" ]] || fail CONTROLLER_NOT_B192A2E5
  hold_lock
  [[ "$(pointer)" == "$OLD_RELEASE" ]] || fail LIVE_RELEASE_CHANGED
  verify_rollback_base
  [[ -f "$CAPP/.env" && -L "$CAPP/storage" ]] || fail CANDIDATE_NOT_MATERIALIZED
  local out; out="$(migration_state after)" || { echo "$out"; fail PRODUCTION_MIGRATION_STATE_UNEXPECTED; }
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
print("APPROVAL=WRITTEN_E5B438_FROM_" + current)
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
  [[ "$(sha "$CTL")" == "$CTL_NEW" ]] || fail CONTROLLER_NOT_B192A2E5
  [[ "$(pointer)" == "$OLD_RELEASE" ]] || { [[ "$(pointer)" == "$NEW_RELEASE" ]] && { mark ACTIVATION ALREADY_ACTIVE; health || :; return 0; }; fail LIVE_RELEASE_UNEXPECTED; }
  grep -q "\"approvedSha\": \"$SHA\"" "$APPROVAL" || fail APPROVAL_NOT_E5B438_RUN_APPROVE
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
  mark ACTIVATION PASS_E5B438_LIVE
}

step_rollback() {
  hold_lock
  [[ "$(pointer)" == "$NEW_RELEASE" ]] || fail ROLLBACK_ONLY_FROM_E5B438
  [[ -d "$ROOTDIR/releases/$OLD_RELEASE/apps/platform" && -L "$ROOTDIR/releases/$OLD_RELEASE/apps/platform/storage" ]] || fail OLD_RELEASE_NOT_READY
  ln -s "releases/$OLD_RELEASE" "$ROOTDIR/.current-rollback-$STAMP"
  mv -f -T -- "$ROOTDIR/.current-rollback-$STAMP" "$CURRENT"
  systemctl reload php8.4-fpm.service
  drop_lock
  mark POINTER "$(pointer)"
  health || :
  restart_queue
  mark ROLLBACK DONE_TO_E71582
}

step_status() {
  mark POINTER "$(pointer)"
  mark CONTROLLER_SHA "$(sha "$CTL")"
  mark APPROVAL_FOR_E5B438 "$(grep -q "\"approvedSha\": \"$SHA\"" "$APPROVAL" && echo yes || echo no)"
  [[ -f "$CAPP/.env" ]] && { migration_state after 2>/dev/null | grep -E '^PRODUCTION_' || :; }
  mark CANDIDATE_STAGED "$([[ -d "$CAND/.git" ]] && echo yes || echo no)"
  mark CANDIDATE_STORAGE_SHARED "$([[ -L "$CAPP/storage" ]] && echo yes || echo no)"
  health || :
}

case "$1" in
  prepare) step_prepare ;;
  storage) step_storage ;;
  materialize) step_materialize ;;
  approve) step_approve ;;
  activate) step_activate ;;
  finish) step_prepare; step_storage; step_materialize; step_approve; step_activate ;;
  rollback) step_rollback ;;
  status) step_status ;;
esac
echo "KMJ_E5B438_RELEASE_STEP=$1 DONE"
