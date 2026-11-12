#!/bin/bash -p
# Exact-SHA owner-only test, inspect and guarded service repair.
set -Eeuo pipefail
umask 077
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
unset BASH_ENV ENV CDPATH LD_PRELOAD LD_LIBRARY_PATH PYTHONPATH PYTHONHOME
fail(){ printf 'KMJ_OFFSITE_P0=BLOCKED_%s\n' "$1" >&2; exit 2; }
[[ $- == *p* && $(id -u) == 0 && $(hostname -s) == KMJ-elite ]] || fail ROOT_ELITE_REQUIRED
[[ $# -eq 1 && $1 == --apply ]] || fail EXACT_OWNER_ACTION_REQUIRED
readonly P=/srv/kmj-codebridge-projects/kmj-main-platform/scripts
readonly A=KMJ_OFFSITE_LEGACY_SFTP_GUARDED_REPAIR_20261111.py
readonly B=test_KMJ_OFFSITE_LEGACY_SFTP_GUARDED_REPAIR_20261111.py
readonly SHA_A=bc33e1f4b471fe4d690bdd172ae61abdb8106f9d67b5ed6595189d7a9514b2da
readonly SHA_B=7dcab9e28751442f3f4f96f6628c32d85cc948c62afc8f492cbe95fadd7e364e
for file in "$P/$A" "$P/$B"; do
  [[ -f $file && ! -L $file ]] || fail SOURCE_ABSENT_OR_SYMLINK
  [[ $(stat -c '%h' -- "$file") == 1 ]] || fail SOURCE_HARDLINK
  [[ $(stat -c '%s' -- "$file") -le 65536 ]] || fail SOURCE_SIZE
 done
D=$(mktemp -d /root/kmj-offsite-guarded.XXXXXXXX) || fail PRIVATE_SCRATCH
[[ -d $D && ! -L $D && $(stat -c '%u:%a' -- "$D") == 0:700 ]] || fail SCRATCH_UNSAFE
cleanup(){
  [[ -d $D && ! -L $D ]] || return 0
  /usr/bin/rm -f -- "$D/$A" "$D/$B"
  /usr/bin/rmdir -- "$D" || true
}
trap cleanup EXIT
/usr/bin/install -m 600 -- "$P/$A" "$D/$A"
/usr/bin/install -m 600 -- "$P/$B" "$D/$B"
printf '%s  %s\n' "$SHA_A" "$D/$A" | /usr/bin/sha256sum -c - || fail REPAIR_SOURCE_SHA
printf '%s  %s\n' "$SHA_B" "$D/$B" | /usr/bin/sha256sum -c - || fail REGRESSION_SOURCE_SHA
/usr/bin/python3 -I -B - "$D/$A" "$D/$B" <<'PY'
import ast, pathlib, sys
for file in sys.argv[1:]:
    ast.parse(pathlib.Path(file).read_bytes(), filename=file)
print('PYTHON_SYNTAX=PASS')
PY
/usr/bin/python3 -I -B -m unittest discover -s "$D" \
  -p 'test_KMJ_OFFSITE_LEGACY_SFTP_GUARDED_REPAIR_20261111.py' -v || fail OFFLINE_REGRESSION
printf 'OFFLINE_REGRESSION=PASS_MOCK_ONLY\n'
/usr/bin/python3 -I -B "$D/$A" --inspect || fail LIVE_READONLY_INSPECT
printf 'ACTUAL_READONLY_HOST_PREFLIGHT=PASS\n'
printf 'ACTIVATION=GUARDED_SINGLE_BACKUP_UNIT\n'
/usr/bin/python3 -I -B "$D/$A" --apply || fail SERVICE_OR_REMOTE_PROOF
printf 'KMJ_OFFSITE_P0=REPAIRED_SERVICE_AND_READBACK_VERIFIED\n'
