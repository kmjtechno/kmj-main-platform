#!/usr/bin/env bash
# KMJ Main Platform e450 independent Google restore: info@google-vps1 only.
# Scoped SFTP-vault import, pinned GitHub source, isolated bwrap restore.
set -Eeuo pipefail
umask 077
fail(){ printf 'GOOGLE_E450_RESTORE=BLOCKED_%s\n' "$1"; exit 2; }
[[ $# == 0 ]] || fail NO_ARGS
[[ $(id -un) == info && $(hostname -s) == google-vps1 ]] || fail EXACT_HOST_AND_INFO_USER
S="$HOME/kmj-recovery-scratch"; V="$HOME/kmj-recovery-vault"
N='offsite-e450c6829cf1.tar.gz.age'
E='a8d4a58f129dbf21ad5d5271e5dea9e12a7cb229a1974f44f9b3feb3da71e4a3'
L='706b735bf8d2dd7712a19f5cfc42fb4bd4b363adf04459eae68dd8af4c9832c5'
D="$S/$N"
[[ -d "$S" && ! -L "$S" && $(stat -c '%u:%a' -- "$S") == "$(id -u):700" ]] || fail PRIVATE_SCRATCH
[[ -f "$HOME/.local/share/kmj-recovery/google-vps-20261019.agekey" &&
   ! -L "$HOME/.local/share/kmj-recovery/google-vps-20261019.agekey" ]] || fail AGE_IDENTITY_UNAVAILABLE
if [[ ! -e "$D" && ! -L "$D" ]]; then
  [[ -d "$V" && ! -L "$V" ]] || fail IMPORT_VAULT_MISSING
  mapfile -d '' -t matches < <(find "$V" -xdev -type f -name "$N" -print0 2>/dev/null)
  [[ ${#matches[@]} == 1 ]] || fail EXPECTED_ONE_VAULT_OBJECT
  python3 -I - "${matches[0]}" "$D" "$E" <<'PY'
import hashlib,os,stat,sys,tempfile
src,dst,expected=sys.argv[1:]
with os.fdopen(os.open(src,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC),'rb') as i:
    st=os.fstat(i.fileno())
    if not (stat.S_ISREG(st.st_mode) and st.st_uid==os.geteuid() and
       stat.S_IMODE(st.st_mode)==0o600 and st.st_nlink==1 and st.st_size==349227):
        raise SystemExit("GOOGLE_IMPORT=BLOCKED_SOURCE_METADATA")
    fd,tmp=tempfile.mkstemp(prefix='.kmj-e450-import-',dir=os.path.dirname(dst))
    try:
        h=hashlib.sha256();total=0
        with os.fdopen(fd,'wb') as o:
            os.fchmod(o.fileno(),0o600)
            for chunk in iter(lambda:i.read(65536),b''):
                total+=len(chunk)
                if total>349227:raise SystemExit("GOOGLE_IMPORT=BLOCKED_SIZE")
                h.update(chunk);o.write(chunk)
            o.flush();os.fsync(o.fileno())
        if total!=349227 or h.hexdigest()!=expected:
            raise SystemExit("GOOGLE_IMPORT=BLOCKED_DIGEST")
        os.link(tmp,dst,follow_symlinks=False)
    finally:
        if os.path.lexists(tmp):os.unlink(tmp)
print("GOOGLE_IMPORT=EXACT_CIPHERTEXT_COPIED")
PY
fi
[[ -f "$D" && ! -L "$D" && $(stat -c '%u:%a:%h:%s' -- "$D") == "$(id -u):600:1:349227" ]] || fail SOURCE_FILE_METADATA
[[ "$(sha256sum -- "$D" | cut -d' ' -f1)" == "$E" ]] || fail ENCRYPTED_SHA256
echo GOOGLE_IMPORT=EXACT_SHA256_PASS
T="$(mktemp -d "$S/kmj-e450-disposable.XXXXXXXX")"
[[ -d "$T" && ! -L "$T" && $(stat -c '%u:%a' -- "$T") == "$(id -u):700" ]] || fail ROOT_SCRATCH
cleanup(){ case "$T" in "$S"/kmj-e450-disposable.*) [[ -d "$T" && ! -L "$T" ]] && rm -rf -- "$T" ;; esac; }
trap cleanup EXIT
mkdir -m 700 -p "$T/scripts/operations"
B='https://raw.githubusercontent.com/kmjtechno/kmj-main-platform/b07a7165373e0f2555f0623713943ea9bba94cea'
download(){
  curl -q -fLSs --retry 2 --connect-timeout 12 --max-time 45 \
    --proto '=https' --proto-redir '=https' --tlsv1.2 "$B/$1" -o "$T/$1" || fail SOURCE_DOWNLOAD
  printf '%s  %s\n' "$2" "$T/$1" | sha256sum -c - >/dev/null || fail SOURCE_DIGEST
}
download scripts/operations/verify-main-platform-google-sftp-restore-20261030.sh adbb341ae298dcfb3ec3e017dcd7010ac4fde47b4a46042afcff6f36ef6a75f2
download scripts/verify_backup_bundle.sh 4e0a7c61f317d1ecacfe6bf8a3c3199bb3fdaaf33b92c23b25e34f45c57de166
download scripts/operations/verify-restored-storage-parity.py a5cc97d5395f7ab4ed5a0a1f426f13a5dd26cfc575323b213276c5cee1bb9171
echo GOOGLE_RESTORE_SOURCE=3_EXACT_SHA256_VERIFIED
KMJ_ACK_ISOLATED_RECOVERY=YES \
KMJ_EXPECTED_ENCRYPTED_SHA256="$E" \
KMJ_EXPECTED_SOURCE_LOCAL_SHA256="$L" \
/bin/bash "$T/scripts/operations/verify-main-platform-google-sftp-restore-20261030.sh" \
 --candidate-sha e450c6829cf19246b658c263abee4ec6c1f77bd6 \
 --expected-release platform-574e443a2c75
echo GOOGLE_E450_RESTORE=INDEPENDENT_DISPOSABLE_PASS
