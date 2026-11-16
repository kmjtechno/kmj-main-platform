#!/bin/bash -p
# P520-only encrypted offsite candidate preparation; never deploys or approves.
set -Eeuo pipefail
umask 077
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
unset BASH_ENV ENV CDPATH LD_PRELOAD LD_LIBRARY_PATH PYTHONPATH PYTHONHOME
block(){ printf 'KMJ_P520_LOCAL_PREP=BLOCKED_%s\n' "$1"; exit 2; }
[[ $# == 1 && ( $1 == --inspect || $1 == --prepare ) ]] || block EXACT_MODE
readonly MODE=$1
readonly SHA=4c9d59103b99a6cfe675bb7b8961fc956eb294f0
readonly PREV=platform-ce6ad7dc9d89
readonly CUR=/home/kmjprod/current
readonly F=/srv/kmj-codebridge-projects/kmj-main-platform/scripts/operations/seal-main-platform-p520-20261116.py
readonly FPIN=f9225fe2eb4270ad81252169500a22e219fa775b37fcf033340a109c9c8b6326
readonly R=/etc/kmj-codebridge/p520-offsite-age-recipient.txt
readonly B=/var/backups/kmj-platform
readonly BASE=https://raw.githubusercontent.com/kmjtechno/kmj-main-platform/5da955a03ccf9b98afc62e138325d454a65dca6d/scripts/operations
[[ $(id -u) == 0 && $(hostname -s) == KMJ-elite && $- == *p* ]] || block PRIVILEGED_HOST
[[ -L $CUR && $(readlink -f "$CUR") == /home/kmjprod/releases/$PREV ]] || block LIVE_DRIFT
[[ -d $B && ! -L $B && $(stat -c %u "$B") == 0 ]] || block BACKUP_ROOT
for file in "/home/kmjprod/releases/platform-4c9d59103b99" \
 "$B/pre-deploy-4c9d59103b99.json" "$B/pre-deploy-4c9d59103b99.tar.gz" \
 "$B/offsite-p520-4c9d59103b99.tar.gz.age"; do
 [[ ! -e $file && ! -L $file ]] || block TARGET_EXISTS
done
[[ -f $R && ! -L $R && $(stat -c '%u:%a:%h' "$R") == 0:600:1 ]] || block RECIPIENT_NOT_OWNER_PINNED
[[ -f $F && ! -L $F && $(sha256sum "$F" | cut -d' ' -f1) == "$FPIN" ]] || block SEAL_SHA_MISMATCH
recipient=$(head -c 256 "$R" | tr -d '\n') || block RECIPIENT_UNREADABLE
[[ $recipient =~ ^age1[023456789acdefghjklmnpqrstuvwxyz]{58}$ ]] || block RECIPIENT_FORMAT
remote=$(git ls-remote --exit-code https://github.com/kmjtechno/kmj-main-platform.git refs/heads/main 2>/dev/null | awk '{print $1}') || block REMOTE_MAIN_UNREACHABLE
[[ $remote == "$SHA" ]] || block MAIN_SHA_DRIFT
echo P520_RECIPIENT_PIN=PASS
echo LIVE_CE6_PREDECESSOR=PASS
echo GOOGLE_REMOTE_REQUIRED=NO
if [[ $MODE == --inspect ]]; then
 echo P520_LOCAL_PREP=INSPECT_PASS_NO_MUTATION
 echo INDEPENDENT_OFFSITE_RESTORE=NOT_VERIFIED
 exit 0
fi
for c in curl age python3 sha256sum mktemp install; do command -v "$c" >/dev/null || block "MISSING_$c"; done
T=$(mktemp -d /root/kmj-p520-4c9.XXXXXXXX) || block ROOT_SCRATCH
[[ ! -L $T && $(stat -c '%u:%a' "$T") == 0:700 ]] || block ROOT_SCRATCH_UNSAFE
cleanup(){ if [[ -d $T && ! -L $T ]]; then rm -f -- "$T/stage.sh" "$T/local.sh" "$T/p520.py"; rmdir -- "$T" || :; fi; }
trap cleanup EXIT
fetch(){
 curl -fsSL --proto '=https' --tlsv1.2 --max-time 45 "$BASE/$1" -o "$T/$2" || block DOWNLOAD
 [[ $(sha256sum "$T/$2" | cut -d' ' -f1) == "$3" ]] || block IMMUTABLE_SOURCE_PIN
}
fetch stage-fast-main-candidate-no-activation.sh stage.sh ebdb77fa56e8e48c32e21d7d1c53a28c56666dd0cc7c002d200706478e1e9a24
fetch prepare-main-platform-local-recovery-exact.sh local.sh 9812f831841ede684cc7a62c378ca35f43fb557dbc402c881785e506b508ff6f
install -o root -g root -m 0500 -T -- "$F" "$T/p520.py"
[[ $(sha256sum "$T/p520.py" | cut -d' ' -f1) == "$FPIN" ]] || block PRIVATE_SEAL_SOURCE_DRIFT
echo PINNED_SCRIPTS=3_SHA256_PASS
bash "$T/stage.sh" "$SHA" || block STAGE
[[ $(readlink -f "$CUR") == /home/kmjprod/releases/$PREV ]] || block LIVE_DRIFT_AFTER_STAGE
bash "$T/local.sh" "$SHA" "$PREV" || block REAL_LOCAL_RESTORE
[[ $(readlink -f "$CUR") == /home/kmjprod/releases/$PREV ]] || block LIVE_DRIFT_AFTER_RESTORE
python3 -I -B "$T/p520.py" --candidate-sha "$SHA" --expected-release "$PREV" || block P520_ENCRYPTION
[[ $(readlink -f "$CUR") == /home/kmjprod/releases/$PREV ]] || block LIVE_DRIFT_AFTER_ENCRYPTION
echo P520_LOCAL_PREP=BUILT_LOCAL_RESTORE_AND_SANITIZED_AGE_ENCRYPTION_PASS
echo P520_REMOTE_READBACK=NOT_VERIFIED
echo P520_INDEPENDENT_RESTORE=NOT_VERIFIED
echo PRODUCTION_APPROVAL=NOT_GRANTED
echo PRODUCTION_RELEASE=UNCHANGED
