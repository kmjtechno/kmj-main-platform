#!/bin/bash -p
# Reviewed operator wrapper for the CD958 live storage cutover (PR #815, commit 1a7f4a88).
# Root on KMJ-elite only. Usage: bash -p <this file> readonly|apply|recover|rollback|materialize
#
# readonly    : build + verify the pinned bundle, create the root-only state dir, run inventory + preflight.
#               No storage, unit, firewall, maintenance, pointer or approval change.
# apply       : guarded storage cutover (short planned downtime), then the pinned materializer if storage completed.
# recover     : reconcile an interrupted transaction from actual state.
# rollback    : only from a paused verified switch whose resume failed.
# materialize : only after storage_complete_materializer_pending.
#
# Git runs only as the project owner. Root never executes project-writable code: it builds the bundle
# from the exact commit's blobs and refuses unless the bytes hash to the reviewed pin below.
# Each operation runs in its own systemd unit, so a dropped terminal cannot interrupt it.
# Results are copied (as the project owner) to work/qa for CodeBridge to read.
set -Eeuo pipefail
umask 077
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
unset BASH_ENV ENV CDPATH
fail() { echo "KMJ_CD958_OPERATOR=BLOCKED $1"; exit 2; }
[[ $- == *p* ]] || fail PRIVILEGED_BASH_REQUIRED
[[ "$#" -eq 1 ]] || fail ONE_STEP_REQUIRED
case "$1" in readonly|apply|recover|rollback|materialize) ;; *) fail UNKNOWN_STEP ;; esac
readonly STEP="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == KMJ-elite ]] || fail ROOT_ELITE_ONLY
readonly P=/srv/kmj-codebridge-projects/kmj-main-platform
readonly COMMIT=1a7f4a883e57a45afd3afc57bb1bce3247107756
readonly BRANCH=review/cd958-storage-cutover-runner
readonly PIN=e64ec2f5ab3d0ed461d5140cd4eb91bdc743b7ae9080ac1fb78be4113a679999
readonly SHA=cd9580701d3cea19d7d4e4c96ebe70c0553fbf37
readonly LIB=/usr/local/libexec/kmj-codebridge
readonly INSTALLED="$LIB/cd958-storage-cutover-1a7f4a8.py"
readonly STATE=/var/lib/kmj-main-platform-live-storage-cutover
[[ -d "$P/.git" && ! -L "$P" ]] || fail PROJECT_CHECKOUT_MISSING
readonly OWNER="$(stat -c %U -- "$P")"
[[ "$OWNER" != root && "$OWNER" =~ ^[a-z_][a-z0-9_-]*$ ]] || fail PROJECT_OWNER_UNEXPECTED
OWNER_HOME="$(getent passwd "$OWNER" | cut -d: -f6)"
readonly OWNER_HOME
as_owner() { runuser -u "$OWNER" -- env -i HOME="$OWNER_HOME" PATH="$PATH" LC_ALL=C GIT_TERMINAL_PROMPT=0 "$@"; }
[[ "$(stat -c '%u:%a' -- "$LIB")" =~ ^0:7[0-5][0-5]$ && ! -L "$LIB" ]] || fail LIB_DIR_UNSAFE

bundle_ok() {
  [[ -f "$INSTALLED" && ! -L "$INSTALLED" ]] || return 1
  [[ "$(stat -c '%u:%g:%a:%h' -- "$INSTALLED")" == "0:0:500:1" ]] || fail INSTALLED_BUNDLE_METADATA_UNSAFE
  [[ "$(sha256sum -- "$INSTALLED" | cut -d' ' -f1)" == "$PIN" ]] || fail INSTALLED_BUNDLE_HASH_MISMATCH
}

ensure_bundle() {
  bundle_ok && return 0
  [[ "$STEP" == readonly ]] || fail RUN_READONLY_STEP_FIRST
  if ! as_owner git -C "$P" cat-file -e "$COMMIT^{commit}" 2>/dev/null; then
    as_owner git -C "$P" fetch --no-tags --quiet origin "+refs/heads/$BRANCH:refs/remotes/origin/$BRANCH" \
      || fail GIT_FETCH_FAILED_AS_PROJECT_OWNER
    as_owner git -C "$P" cat-file -e "$COMMIT^{commit}" || fail REVIEWED_COMMIT_NOT_FETCHED
  fi
  local work
  work="$(mktemp -d /root/kmj-cd958-bundle.XXXXXX)"
  for name in orchestrator native_plan native_ops cutover_runner; do
    as_owner git -C "$P" show "$COMMIT:scripts/operations/cd958-cutover-review/$name.py" >"$work/$name.py" \
      || fail GIT_SHOW_FAILED
  done
  # Same construction as build_cutover_bundle.py, inline so no checkout code runs as root.
  /usr/bin/python3 -I -B - "$work" "$PIN" "$LIB" "$(basename -- "$INSTALLED")" <<'KMJ_BUILD'
import hashlib, os, sys
work, pin, lib, final = sys.argv[1:]
chunks = ["import sys\nimport types\n"]
for name in ("orchestrator", "native_plan", "native_ops", "cutover_runner"):
    with open(os.path.join(work, name + ".py"), "rb") as stream:
        source = stream.read()
    compile(source, name + ".py", "exec")
    chunks.append(f"module = types.ModuleType({name!r})\n"
                  f"sys.modules[{name!r}] = module\n"
                  f"exec(compile({source!r}, {name + '.py'!r}, 'exec'), module.__dict__)\n")
chunks.append("raise SystemExit(module.main())\n")
bundle = "".join(chunks).encode("utf-8")
if hashlib.sha256(bundle).hexdigest() != pin:
    print("KMJ_CD958_OPERATOR=BLOCKED BUILT_BUNDLE_HASH_MISMATCH"); raise SystemExit(2)
directory = os.open(lib, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
temporary = ".cd958-bundle-" + os.urandom(8).hex()
fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o500, dir_fd=directory)
try:
    view = memoryview(bundle)
    while view:
        view = view[os.write(fd, view):]
    os.fchown(fd, 0, 0); os.fchmod(fd, 0o500); os.fsync(fd)
finally:
    os.close(fd)
try:
    os.link(temporary, final, src_dir_fd=directory, dst_dir_fd=directory)  # fails if final already exists
finally:
    os.unlink(temporary, dir_fd=directory)
os.fsync(directory); os.close(directory)
print("BUNDLE_INSTALLED=" + pin)
KMJ_BUILD
  rm -r -- "$work"
  bundle_ok || fail BUNDLE_INSTALL_NOT_VERIFIED
}

ensure_state() {
  if [[ ! -e "$STATE" ]]; then
    [[ "$STEP" == readonly ]] || fail RUN_READONLY_STEP_FIRST
    install -d -m 0700 -o root -g root -- "$STATE"
  fi
  [[ -d "$STATE" && ! -L "$STATE" && "$(stat -c '%u:%g:%a' -- "$STATE")" == "0:0:700" ]] || fail STATE_DIR_UNSAFE
}

LAST_RC=0
run_op() {
  local op="$1" ts out unit receipt
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  out="/root/kmj-cd958-$op-$ts.json"
  unit="kmj-cd958-$op-$ts"
  set +e
  systemd-run --unit="$unit" --wait --collect --quiet -p Type=exec \
    -p StandardOutput=truncate:"$out" -p StandardError=journal \
    /usr/bin/python3 -I -B "$INSTALLED" "$op" "$SHA"
  LAST_RC=$?
  set -e
  receipt="KMJ_CD958_CUTOVER_${op^^}_${ts}.json"
  as_owner tee -- "$P/work/qa/$receipt" <"$out" >/dev/null || echo "RECEIPT_COPY_FAILED $out"
  echo "== $op rc=$LAST_RC receipt=work/qa/$receipt unit=$unit"
  head -c 4000 -- "$out"; echo
}

ensure_bundle
ensure_state
case "$STEP" in
  readonly)
    run_op inventory
    run_op preflight
    ;;
  apply)
    run_op apply
    if [[ "$LAST_RC" == 0 ]]; then run_op materialize; fi
    ;;
  *) run_op "$STEP" ;;
esac
echo "KMJ_CD958_OPERATOR_STEP=$STEP DONE rc=$LAST_RC"
exit "$LAST_RC"
