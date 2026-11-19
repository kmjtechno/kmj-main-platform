#!/usr/bin/env bash
# KMJ P520 current-CE6 to draft-Licensing-Hub independent recovery source doctor.
# READ-ONLY. NO backup, encryption, transfer, key change, release or approval.
set -Eeuo pipefail
umask 077
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
unset BASH_ENV ENV CDPATH LD_PRELOAD LD_LIBRARY_PATH PYTHONPATH PYTHONHOME
block(){ printf 'KMJ_P520_V2_SOURCE_DOCTOR=BLOCKED_%s\n' "$1"; printf 'PRODUCTION_APPROVAL=NOT_GRANTED\n'; exit 2; }

[[ $# -eq 1 && "$1" == '--inspect' ]] || block 'EXACT_READONLY_MODE'
[[ "$(id -u)" -eq 0 && "$(hostname -s)" == 'KMJ-elite' ]] || block 'OWNER_ELITE_ROOT_REQUIRED'
readonly CUR='/home/kmjprod/current'
readonly EXPECTED_CURRENT='/home/kmjprod/releases/platform-ce6ad7dc9d89'
readonly CANDIDATE='bd8975f0ee888a26013a6669e687db540f39f440'
readonly CANDIDATE_SHORT='bd8975f0ee88'
readonly ROOT='/var/backups/kmj-platform'
readonly TRUST='/etc/kmj-p520-restore-trust'
readonly EXPECTED_SIGNING_KEY_SHA='6216f2bc0bd7b63bea2f15bc771494fa6e2ab2fcfca01e75761a113120be81c4'
readonly EXPECTED_AGE='age1jgk7wrgccyu8s7wlh6zpxnm4qdvfus0d5t092s9zkjjmtwe8efjstvcs5u'
readonly KEY="$TRUST/p520-receipt-ed25519-public.pem"
readonly AGE="$TRUST/p520-age-recipient.txt"

[[ -L "$CUR" && "$(readlink -f -- "$CUR")" == "$EXPECTED_CURRENT" ]] || block 'LIVE_CE6_POINTER_DRIFT'
[[ -d "$ROOT" && ! -L "$ROOT" && "$(stat -c '%u' -- "$ROOT")" == 0 ]] || block 'BACKUP_ROOT_UNTRUSTED'
[[ -d "$TRUST" && ! -L "$TRUST" && "$(stat -c '%u:%g:%a' -- "$TRUST")" == '0:0:700' ]] || block 'ELITE_TRUST_DIR_UNTRUSTED'
for name in "$KEY" "$AGE"; do
  [[ -f "$name" && ! -L "$name" && "$(stat -c '%u:%g:%a:%h' -- "$name")" == '0:0:600:1' ]] || block 'PUBLIC_IDENTITY_FILE_METADATA'
done
[[ "$(sha256sum -- "$KEY" | cut -d' ' -f1)" == "$EXPECTED_SIGNING_KEY_SHA" ]] || block 'ED25519_PIN_MISMATCH'
[[ "$(cat -- "$AGE")" == "$EXPECTED_AGE" ]] || block 'AGE_RECIPIENT_PIN_MISMATCH'
[[ "$(wc -c < "$AGE")" -eq 63 ]] || block 'AGE_RECIPIENT_BYTES'
command -v openssl >/dev/null || block 'OPENSSL_MISSING'
openssl pkey -pubin -in "$KEY" -noout >/dev/null 2>&1 || block 'ED25519_PUBLIC_PEM_INVALID'
command -v age >/dev/null || block 'AGE_MISSING'
command -v python3 >/dev/null || block 'PYTHON_MISSING'
printf 'P520_ELITE_TRUSTED_PUBLIC_PIN=PASS\n'
printf 'P520_LIVE_CURRENT_CE6=PASS\n'
printf 'P520_DRAFT_CANDIDATE_SHA=%s\n' "$CANDIDATE"
printf 'P520_DRAFT_SHA_OWNER_RELEASE_APPROVAL=NOT_GRANTED\n'

readonly CANDIDATE_RELEASE="/home/kmjprod/releases/platform-$CANDIDATE_SHORT"
readonly ARCHIVE="$ROOT/pre-deploy-$CANDIDATE_SHORT.tar.gz"
readonly WITNESS="$ROOT/pre-deploy-$CANDIDATE_SHORT.json"
readonly OUT="$ROOT/offsite-p520-$CANDIDATE_SHORT.tar.gz.age"

for item in "$CANDIDATE_RELEASE" "$ARCHIVE" "$WITNESS" "$OUT"; do
  [[ ! -L "$item" ]] || block 'SYMLINKED_CANDIDATE_SOURCE'
done
if [[ -d "$CANDIDATE_RELEASE" ]]; then
  echo 'P520_CANDIDATE_RELEASE_DIRECTORY=PRESENT_UNATTESTED'
else
  echo 'P520_CANDIDATE_RELEASE_DIRECTORY=MISSING'
fi
if [[ -f "$ARCHIVE" && -f "$WITNESS" ]]; then
  for item in "$ARCHIVE" "$WITNESS"; do
    [[ "$(stat -c '%u:%a:%h' -- "$item")" == '0:600:1' ]] || block 'CANDIDATE_WITNESS_METADATA'
  done
  # Only bounded witness metadata; no user-controlled paths or shell.
  python3 -I -B - "$WITNESS" "$ARCHIVE" "$CANDIDATE" <<'PY'
import hashlib,json,os,re,stat,sys
witness,archive,candidate=sys.argv[1:]
try:
    if os.stat(witness).st_size>16384:raise ValueError
    with open(witness,'rb') as f: record=json.load(f)
    if not isinstance(record,dict) or record.get('approvedSha')!=candidate or record.get('currentRelease')!='platform-ce6ad7dc9d89':raise ValueError
    expected=record.get('backupSha256')
    if not isinstance(expected,str) or not re.fullmatch('[0-9a-f]{64}',expected):raise ValueError
    digest=hashlib.sha256()
    with open(archive,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):digest.update(chunk)
    if digest.hexdigest()!=expected:raise ValueError
except (OSError,ValueError,TypeError,KeyError,json.JSONDecodeError):
    print('P520_CANDIDATE_LOCAL_WITNESS=BLOCKED_IDENTITY_OR_SHA256')
    sys.exit(2)
print('P520_CANDIDATE_LOCAL_WITNESS=PASS_BYTES_IDENTITY_ONLY')
PY
  [[ $? == 0 ]] || block 'CANDIDATE_LOCAL_WITNESS'
else
  if [[ -e "$ARCHIVE" || -e "$WITNESS" ]]; then
    echo 'P520_CANDIDATE_LOCAL_WITNESS=BLOCKED_INCOMPLETE_PAIR'
  else
    echo 'P520_CANDIDATE_LOCAL_WITNESS=MISSING'
  fi
fi
if [[ -f "$OUT" ]]; then
  [[ "$(stat -c '%u:%a:%h' -- "$OUT")" == '0:600:1' ]] || block 'ENCRYPTED_CIPHER_METADATA'
  echo 'P520_CANDIDATE_CIPHER=PRESENT_UNVERIFIED_RECIPIENT_OR_TRANSFER'
else
  echo 'P520_CANDIDATE_CIPHER=NOT_CREATED'
fi
echo 'P520_DRAFT_CANDIDATE_RELEASE_STAGING=NOT_ATTESTED'
echo 'P520_NEW_P520_ENCRYPTION_TRANSFER_RESTORE=NOT_VERIFIED'
echo 'P520_PRODUCTION_PROTECTED_PREDECESSOR_MATCH=BLOCKED_E5B_VS_CE6'
echo 'P520_PRODUCTION_OR_BACKUP_MUTATION=NONE'
echo 'PRODUCTION_APPROVAL=NOT_GRANTED'
echo 'KMJ_P520_V2_SOURCE_DOCTOR=READ_ONLY_COMPLETE'
