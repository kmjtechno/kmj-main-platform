#!/usr/bin/env bash
# Owner-only post-IP-rotation offsite recovery receiver evidence.
# No backup service start, no drop-in, no key or firewall changes.
set -Eeuo pipefail
umask 077
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
unset BASH_ENV ENV CDPATH LD_PRELOAD LD_LIBRARY_PATH PYTHONPATH PYTHONHOME
deny() { printf 'KMJ_POST_IP_OFFSITE=BLOCKED_%s\n' "$1" >&2; exit 2; }
[[ $# == 0 && $(/usr/bin/id -u) == 0 && $(/usr/bin/hostname -s) == KMJ-elite ]] || deny ROOT_HOST_OR_ARGUMENTS
[[ -f /usr/bin/curl && ! -L /usr/bin/curl ]] || deny HTTPS_CLIENT_UNAVAILABLE

# No public address is discovered from untrusted keyscan output or a stale /etc/hosts.
# Confirm ELITE's egress NAT path independently before contacting Google receiver.
actual=$(/usr/bin/curl --noproxy '*' --proto '=https' --tlsv1.2 \
    --fail --silent --show-error --connect-timeout 6 --max-time 18 \
    'https://api.ipify.org') || deny PUBLIC_EGRESS_UNVERIFIED
[[ "$actual" == "150.242.200.81" ]] || deny EGRESS_NOT_NEW_ELITE_IP
printf 'ELITE_POST_ROTATION_EGRESS=150.242.200.81_VERIFIED\n'

P=/srv/kmj-codebridge-projects/kmj-main-platform/scripts
F="$P/KMJ_OFFSITE_LEGACY_255_ONEPASS_20261111.py"
[[ -f "$F" && ! -L "$F" && $(/usr/bin/stat -c %h -- "$F") == 1 ]] || deny PINNED_PROBE_SOURCE_UNSAFE
T=$(/usr/bin/mktemp -d /root/kmj-post-ip-offsite.XXXXXXXX) || deny PRIVATE_TEMP_FAILURE
cleanup() {
    if [[ -d "$T" && ! -L "$T" ]]; then
        /usr/bin/rm -f -- "$T/onepass.py"
        /usr/bin/rmdir -- "$T" || true
    fi
}
trap cleanup EXIT
[[ "$(/usr/bin/stat -c '%u:%a' -- "$T")" == 0:700 ]] || deny PRIVATE_TEMP_UNSAFE
/usr/bin/install -m 600 -- "$F" "$T/onepass.py"
printf '%s  %s\n' \
    '1d21d2f7582de82875a88373cbb993c174ebbc5351ac708c9fec055db42fcfb1' \
    "$T/onepass.py" | /usr/bin/sha256sum -c - || deny PROBE_SOURCE_DRIFT

/usr/bin/python3 -I -B - "$T/onepass.py" <<'PY'
import ast, pathlib, sys
ast.parse(pathlib.Path(sys.argv[1]).read_bytes(), filename=sys.argv[1])
print("PROBE_SYNTAX=PASS", flush=True)
PY

/usr/bin/env -i PATH="$PATH" HOME=/root LANG=C LC_ALL=C \
  /usr/bin/python3 -I -B "$T/onepass.py" || deny PINNED_TRANSPORT_CANARY_FAILED

printf 'POST_ROTATION_RESTRICTED_SFTP_CANARY=PASS\n'
printf 'SERVICE_EXECUTION=NOT_RUN\n'
printf 'EXIT_255=NOT_RESOLVED_BY_THIS_PROBE\n'
printf 'INDEPENDENT_RESTORE=NOT_VERIFIED\n'
