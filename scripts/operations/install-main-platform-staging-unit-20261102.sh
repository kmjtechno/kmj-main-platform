#!/bin/bash -p
# KMJ TECHNO: owner-only staging runner/unit publication, source-contract v1.
# --inspect is read-only. --install requires root on KMJ-elite and a reviewed
# root-owned immutable snapshot. It installs ABSENT targets only; never starts
# staging or production, changes a release pointer, or grants approval.
set -Eeuo pipefail
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
umask 077
block() { printf 'KMJ_STAGING_OWNER_INSTALL=BLOCKED_%s\n' "$1"; exit 2; }
[[ $- == *p* ]] || block PRIVILEGED_BASH_REQUIRED
[[ $# -eq 1 && ( $1 == --inspect || $1 == --install ) ]] || block ARGUMENTS
mode=$1
dir="$(cd -- "$(dirname -- "$0")" && pwd -P)"
root="$(dirname -- "$(dirname -- "$dir")")"
runner="$root/deploy/staging/kmj-main-platform-staging-deploy.sh"
unit="$root/deploy/staging/kmj-main-platform-staging-deploy.service"
runner_blob=39fd993d4bc2cd4427fc6d460073204a7e1f82e3
unit_blob=07d77b4e2ec9b2e3cd73d4a8aa4c4786e5927eb1
runner_sha256=9713b608e2cd8c8c9f0ad4f56e475f035b86bf889ef0cc164f9aa9532ad2d7ab
unit_sha256=21e8566433cfbb7c86864844df68295fb1dd420b87ec21aa541a35a1656c9919
sha_file() { /usr/bin/sha256sum -- "$1" | /usr/bin/cut -d ' ' -f1; }
[[ -f "$runner" && ! -L "$runner" && -f "$unit" && ! -L "$unit" ]] || block SOURCE_ABSENT_OR_LINKED
[[ "$(/usr/bin/git hash-object -- "$runner")" == "$runner_blob" ]] || block RUNNER_SOURCE_BLOB
[[ "$(/usr/bin/git hash-object -- "$unit")" == "$unit_blob" ]] || block UNIT_SOURCE_BLOB
[[ "$(sha_file "$runner")" == "$runner_sha256" ]] || block RUNNER_SOURCE_SHA256
[[ "$(sha_file "$unit")" == "$unit_sha256" ]] || block UNIT_SOURCE_SHA256
/usr/bin/bash -n -- "$runner" || block RUNNER_SYNTAX
[[ "$(/usr/bin/grep -c '^ExecStart=' -- "$unit")" == 1 ]] || block UNIT_MULTIPLE_EXEC
/usr/bin/grep -Fxq 'ExecStart=/usr/bin/bash /usr/local/libexec/kmj-codebridge/kmj-main-platform-staging-deploy.sh' -- "$unit" || block UNIT_EXEC
if [[ $mode == --inspect ]]; then
  printf 'KMJ_STAGING_OWNER_SOURCE=EXACT_GIT_BLOBS_AND_SHA256_PASS\n'
  printf 'KMJ_STAGING_OWNER_INSTALL=INSPECT_ONLY\n'
  printf 'KMJ_STAGING_ACTIVATION=NOT_ATTEMPTED\n'
  exit 0
fi
[[ $(id -u) == 0 && $(hostname -s) == KMJ-elite ]] || block OWNER_HOST
[[ $root =~ ^/root/kmj-approved/[a-f0-9]{40}$ ]] || block SNAPSHOT_PATH
protected_dir() {
  local d=$1 bits
  [[ -d $d && ! -L $d && $(stat -c %u -- "$d") == 0 ]] || return 1
  bits="$(stat -c %a -- "$d")"
  (( (8#$bits & 8#022) == 0 ))
}
protected_source() {
  local f=$1 bits
  [[ -f $f && ! -L $f && $(stat -c '%u:%h' -- "$f") == '0:1' ]] || return 1
  bits="$(stat -c %a -- "$f")"
  (( (8#$bits & 8#022) == 0 ))
}
for d in / /root /root/kmj-approved "$root" "$root/scripts" "$dir" "$root/deploy" "$root/deploy/staging" /usr /usr/local /usr/local/libexec /etc /etc/systemd /etc/systemd/system; do
  protected_dir "$d" || block SOURCE_OR_TARGET_ANCESTOR
done
for f in "$0" "$runner" "$unit"; do
  protected_source "$f" || block SOURCE_METADATA
done
dest_dir=/usr/local/libexec/kmj-codebridge
if [[ ! -e $dest_dir && ! -L $dest_dir ]]; then
  /usr/bin/install -d -o root -g root -m 0755 -- "$dest_dir" || block DEST_DIR_CREATE
fi
protected_dir "$dest_dir" || block DEST_DIR_METADATA
target_runner="$dest_dir/kmj-main-platform-staging-deploy.sh"
target_unit=/etc/systemd/system/kmj-main-platform-staging-deploy.service
[[ ! -e $target_runner && ! -L $target_runner ]] || block RUNNER_ALREADY_EXISTS
[[ ! -e $target_unit && ! -L $target_unit ]] || block UNIT_ALREADY_EXISTS
# Roll back only files this invocation created, bound to the original inode and SHA256.
# A partial two-file install must never strand a runner or unit that blocks retry.
created_runner_inode=
created_unit_inode=
install_committed=NO
remove_if_ours() {
  local dest=$1 inode=$2 digest=$3
  [[ -n "$inode" && -f "$dest" && ! -L "$dest" ]] || return 0
  [[ "$(stat -c '%d:%i:%u:%g:%h' -- "$dest" 2>/dev/null)" == "$inode:0:0:1" ]] || return 0
  [[ "$(sha_file "$dest")" == "$digest" ]] || return 0
  /usr/bin/rm -f -- "$dest"
}
rollback_partial_install() {
  local prior=$?
  if [[ "$install_committed" != YES ]]; then
    remove_if_ours "$target_unit" "$created_unit_inode" "$unit_sha256" || :
    remove_if_ours "$target_runner" "$created_runner_inode" "$runner_sha256" || :
    # If manager saw an intermediate unit, clear that state without starting it.
    if [[ -n "$created_unit_inode" ]]; then
      /usr/bin/systemctl daemon-reload >/dev/null 2>&1 || :
    fi
    if [[ -n "$created_runner_inode" || -n "$created_unit_inode" ]]; then
      printf 'KMJ_STAGING_OWNER_PARTIAL_ROLLBACK=ATTEMPTED_VERIFY_TARGETS\n'
    fi
  fi
  return "$prior"
}
trap rollback_partial_install EXIT
publish() {
  local src=$1 dest=$2 perms=$3 expected=$4 expected256=$5 tmp
  tmp="$(/usr/bin/mktemp "$(dirname -- "$dest")/.kmj-stage-owner.XXXXXXXX")" || block TEMP
  # Temporary file is root-owned and private; clean up only our own temp path.
  /usr/bin/install -o root -g root -m "$perms" -T -- "$src" "$tmp" || { /usr/bin/rm -f -- "$tmp"; block COPY; }
  if [[ "$(/usr/bin/git hash-object -- "$tmp")" != "$expected" || "$(sha_file "$tmp")" != "$expected256" ]]; then
    /usr/bin/rm -f -- "$tmp"; block STAGED_HASH
  fi
  local published_inode
  published_inode="$(stat -c '%d:%i' -- "$tmp")" || { /usr/bin/rm -f -- "$tmp"; block TEMP_INODE; }
  if ! /usr/bin/ln -T -- "$tmp" "$dest"; then
    /usr/bin/rm -f -- "$tmp"; block NO_CLOBBER_LINK
  fi
  if [[ "$dest" == "$target_runner" ]]; then
    created_runner_inode="$published_inode"
  elif [[ "$dest" == "$target_unit" ]]; then
    created_unit_inode="$published_inode"
  else
    block TARGET_UNRECOGNIZED
  fi
  /usr/bin/rm -f -- "$tmp"
  [[ -f "$dest" && ! -L "$dest" && $(stat -c '%u:%g:%a:%h' -- "$dest") == "0:0:$perms:1" ]] || block TARGET_METADATA
  [[ "$(/usr/bin/git hash-object -- "$dest")" == "$expected" && "$(sha_file "$dest")" == "$expected256" ]] || block TARGET_HASHES
}
publish "$runner" "$target_runner" 750 "$runner_blob" "$runner_sha256"
publish "$unit" "$target_unit" 644 "$unit_blob" "$unit_sha256"
# A manager reload is not a service start, release switch or approval.
# Any failure leaves an inactive, reviewed operator-install to investigate.
if ! /usr/bin/systemctl daemon-reload; then block DAEMON_RELOAD; fi
install_committed=YES
printf 'KMJ_STAGING_OWNER_SOURCE=EXACT_GIT_BLOBS_AND_SHA256_PASS\n'
printf 'KMJ_STAGING_OWNER_INSTALL=INSTALLED_INACTIVE_PENDING_APPROVAL\n'
printf 'KMJ_STAGING_ACTIVATION=NOT_ATTEMPTED\n'
printf 'KMJ_PRODUCTION_CHANGED=NO\n'
