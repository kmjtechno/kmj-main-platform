#!/usr/bin/env bash
# Owner-run, root-only installer for the 4-lineage V3 health guard (does NOT start a backup).
#
# Usage: kmj-v3-install-4-lineage-guard.sh /path/to/KMJ_OFFSITE_V3_DUAL_LOCAL_HEALTH_ONEPASS_20261126.py
# Steps (fail closed, each step verified):
#  1. sha256 of the given file must equal the pin below.
#  2. offline --selftest must pass.
#  3. install it root:root 0600 as <libexec>/kmj-v3-dual-local-health-onepass-20261126.py
#     with a matching .sha256 file (the unit's ExecStartPre checks it).
#  4. back up the unit, repoint ONLY the two ExecStart* lines, daemon-reload.
#  5. run the new guard's read-only --preflight once and report its exit.
# Rollback: cp the printed unit backup over the unit and run systemctl daemon-reload.
# Env (tests): KMJ_LIBEXEC, KMJ_UNIT, KMJ_PIN, KMJ_SKIP_SYSTEMCTL, KMJ_ALLOW_NONROOT_FOR_TESTS
set -Eeuo pipefail
umask 077

PIN="${KMJ_PIN:-c772dd3efb0303523530558b8b233fe2fd62e7fb9d105c3f3533a21be768e0f7}"
LIBEXEC="${KMJ_LIBEXEC:-/usr/local/libexec}"
UNIT="${KMJ_UNIT:-/etc/systemd/system/kmj-v3-dual-local-health.service}"
OLD="kmj-v3-dual-local-health-onepass-20261118"
NEW="kmj-v3-dual-local-health-onepass-20261126"

fail() { echo "V3_GUARD_INSTALL=FAIL:$1" >&2; exit "${2:-1}"; }
[[ "$(id -u)" == 0 || "${KMJ_ALLOW_NONROOT_FOR_TESTS:-}" == 1 ]] || fail ROOT_REQUIRED 2
src="${1:-}"
[[ -n "$src" && -f "$src" && ! -L "$src" ]] || fail SOURCE_FILE_MISSING 2
[[ "$(sha256sum "$src" | cut -d' ' -f1)" == "$PIN" ]] || fail SOURCE_SHA_MISMATCH 3
[[ -f "$UNIT" && ! -L "$UNIT" ]] || fail UNIT_MISSING 4
grep -q "^ExecStart=/usr/bin/python3 -I -B $LIBEXEC/$OLD.py --run-once-local\$" "$UNIT" || fail UNIT_EXECSTART_UNEXPECTED 4
grep -q "^ExecStartPre=/usr/bin/sha256sum --check --status $LIBEXEC/$OLD.sha256\$" "$UNIT" || fail UNIT_EXECSTARTPRE_UNEXPECTED 4
[[ ! -e "$LIBEXEC/$NEW.py" ]] || fail ALREADY_INSTALLED 5

python3 -I -B "$src" --selftest >/dev/null 2>&1 || fail SELFTEST_FAILED 6

install -m 0600 -o root -g root "$src" "$LIBEXEC/$NEW.py"
( cd "$LIBEXEC" && sha256sum "$NEW.py" > "$NEW.sha256" && chmod 0600 "$NEW.sha256" && sha256sum --check --status "$NEW.sha256" ) || fail INSTALLED_FILE_HASH 7

backup="$UNIT.bak.$(date -u +%Y%m%dT%H%M%SZ)"
cp -p "$UNIT" "$backup"
sed -i "s#$OLD\\.sha256#$NEW.sha256#; s#$OLD\\.py#$NEW.py#" "$UNIT"
grep -q "$NEW.py --run-once-local" "$UNIT" && grep -q "$NEW.sha256" "$UNIT" || { cp -p "$backup" "$UNIT"; fail UNIT_EDIT_VERIFY 8; }
[[ "${KMJ_SKIP_SYSTEMCTL:-}" == 1 ]] || systemctl daemon-reload

rc=0
if [[ "${KMJ_SKIP_SYSTEMCTL:-}" != 1 ]]; then
  python3 -I -B "$LIBEXEC/$NEW.py" --preflight >/dev/null 2>&1 || rc=$?
fi
echo "V3_GUARD_INSTALL=DONE"
echo "UNIT_BACKUP=$backup"
echo "PREFLIGHT_EXIT=$rc"
echo "BACKUP_NOT_STARTED=YES"
