#!/bin/bash -p
# KMJ P0: strict read-only failed preflight classification. NEVER apply.
set -Eeuo pipefail
umask 077
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
unset BASH_ENV ENV CDPATH LD_PRELOAD LD_LIBRARY_PATH GIT_DIR GIT_WORK_TREE PYTHONPATH PYTHONHOME
block(){ printf 'KMJ_P0_DIAG=BLOCKED_%s\n' "$1" >&2; exit 2; }
[[ $- == *p* && $# -eq 0 ]] || block INVOCATION
[[ $(id -u) == 0 && $(hostname -s) == KMJ-elite ]] || block ROOT_HOST
readonly P=/srv/kmj-codebridge-projects/kmj-main-platform/scripts
readonly A=KMJ_OFFSITE_LEGACY_SFTP_GUARDED_REPAIR_20261111.py
readonly B=test_KMJ_OFFSITE_LEGACY_SFTP_GUARDED_REPAIR_20261111.py
readonly SHA_A=142ea8eb22904ec8bf5f165a2ec04049893f4d85aff50967a185d62f7cf13249
readonly SHA_B=09c8239a2ff22d289181e9bc5465942d9f451f191df9da299b3ebc325bca417a
for file in "$P/$A" "$P/$B"; do
  [[ -f $file && ! -L $file ]] || block SOURCE_UNSAFE
  [[ $(stat -c '%h' -- "$file") == 1 ]] || block SOURCE_HARDLINK
  [[ $(stat -c '%s' -- "$file") -le 65536 ]] || block SOURCE_OVERSIZED
done
D=$(/usr/bin/mktemp -d /root/kmj-offsite-readonly.XXXXXXXX) || block PRIVATE_SCRATCH
[[ -d $D && ! -L $D && $(stat -c '%u:%a' -- "$D") == 0:700 ]] || block SCRATCH_UNSAFE
cleanup(){
  [[ -d $D && ! -L $D ]] || return 0
  /usr/bin/rm -f -- "$D/$A" "$D/$B"
  /usr/bin/rmdir -- "$D" || true
}
trap cleanup EXIT
/usr/bin/install -m 600 -- "$P/$A" "$D/$A"
/usr/bin/install -m 600 -- "$P/$B" "$D/$B"
printf '%s  %s\n' "$SHA_A" "$D/$A" | /usr/bin/sha256sum -c - || block SOURCE_HASH
printf '%s  %s\n' "$SHA_B" "$D/$B" | /usr/bin/sha256sum -c - || block TEST_HASH
/usr/bin/python3 -I -B - "$D/$A" "$D/$B" <<'PY'
import ast, pathlib, sys
for p in sys.argv[1:]:
    ast.parse(pathlib.Path(p).read_bytes(), filename=p)
print("SOURCE_SYNTAX=PASS")
PY
/usr/bin/python3 -I -B -m unittest discover -s "$D" \
-p 'test_KMJ_OFFSITE_LEGACY_SFTP_GUARDED_REPAIR_20261111.py' -q || block OFFLINE_TEST
printf 'OFFLINE_TEST=PASS\n'
# Do not invoke --apply or systemctl start; tail review only classifies text shape.
/usr/bin/env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin HOME=/root LANG=C LC_ALL=C \
  /usr/bin/python3 -I -B "$D/$A" --tail-review || block TAIL_READONLY_PRECHECK
printf 'KMJ_P0_DIAG=TAIL_CLASSIFIED_NO_ACTIVATION\n'
