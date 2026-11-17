#!/bin/bash -p
# Google VPS nonroot restore ONLY 20261117T125803Z exact SHA-pinned age ciphertext.
# Key in decryption bwrap ONLY; no key in tar/postgres bwrap. Never production.
set -Eeuo pipefail
umask 077
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
unset BASH_ENV ENV CDPATH LD_PRELOAD LD_LIBRARY_PATH PYTHONPATH PYTHONHOME
unset PGHOST PGPORT PGDATABASE PGUSER PGPASSWORD PGSERVICE PGSERVICEFILE PGOPTIONS
unset DB_URL DATABASE_URL BACKUP_DATABASE_URL
blocked(){ printf 'KMJ_GOOGLE_V3_NOV17_RESTORE=BLOCKED_%s\n' "$1"; exit 3; }
[[ $# == 1 && "$1" == --restore-once && $- == *p* ]] || blocked ARGS
[[ "$(id -u)" != 0 && "$(id -un)" == info && "$(hostname -s)" == google-vps1 && "$HOME" == /home/info ]] || blocked HOST_USER
P=/home/info/kmj-cloudos/scripts
A=KMJ_GOOGLE_V3_20261117_RESTORE_HELPER.py
B=test_KMJ_GOOGLE_V3_20261117_RESTORE_HELPER.py
C=KMJ_GOOGLE_X25519_EXACT_PGDMP_RESTORE_HELPER_20261112.py
R=/home/info/kmj-recovery-scratch
KEY=/home/info/.local/share/kmj-recovery/google-vps-20261019.agekey
UID_EXPECT=$(id -u)
[[ -f "$P/$A" && -f "$P/$B" && -f "$P/$C" && ! -L "$P/$A" && ! -L "$P/$B" && ! -L "$P/$C" ]] || blocked SOURCE_MISSING
printf '%s  %s\n' \
'c72476c4be2648e3ed31457334b7e5acba56d52084e5059c932ffd4bf45fcc9c' "$P/$A" \
'db33552104f6e8c51c03d931bb90d280f7c062bc6ecb6892775e7fa42228d2be' "$P/$B" \
'b20e55f1de13d8bae3f6e4156dafc135002b4d73215bf3f5613359419c893f26' "$P/$C" \
| sha256sum -c - || blocked HELPER_SHA
python3 -I -B - "$P/$A" "$P/$B" "$P/$C" <<'PY'
import ast,pathlib,sys
for f in sys.argv[1:]:ast.parse(pathlib.Path(f).read_bytes(),filename=f)
print("KMJ_V3_NOV17_PGDMP_RESTORE_AST=3_PASS")
PY
python3 -I -B -m unittest discover -s "$P" \
 -p 'test_KMJ_GOOGLE_V3_20261117_RESTORE_HELPER.py' -v || blocked TESTS
echo 'KMJ_V3_NOV17_PGDMP_RESTORE_FIXTURES=PASS'
python3 -I -B "$P/$A" --selftest || blocked SELFTEST
[[ -d "$R" && ! -L "$R" && "$(stat -c '%u:%a' "$R")" == "$UID_EXPECT:700" ]] || blocked SCRATCH_DIR
[[ -f "$KEY" && ! -L "$KEY" && "$(stat -c '%u:%a:%h' "$KEY")" == "$UID_EXPECT:600:1" ]] || blocked KEY_META
for bin in /usr/bin/age /usr/bin/bwrap /usr/bin/timeout /usr/bin/python3 /usr/bin/mktemp; do
  [[ -x "$bin" ]] || blocked TOOL_MISSING
done
PGBIN=''
for dir in /usr/lib/postgresql/*/bin; do
  [[ -x "$dir/initdb" && -x "$dir/pg_ctl" && -x "$dir/createdb" && -x "$dir/psql" && -x "$dir/pg_restore" ]] && PGBIN=$dir
done
[[ -n "$PGBIN" ]] || blocked PGBIN_MISSING
FREE_KIB=$(df -Pk "$R" | awk 'END {print $4}')
[[ "$FREE_KIB" =~ ^[0-9]+$ && "$FREE_KIB" -ge 1048576 ]] || blocked FREE_SPACE_1GIB
T=$(mktemp -d "$R/kmj-x25519-disposable.XXXXXXXXXXXX") || blocked WORK_CREATE
[[ -d "$T" && ! -L "$T" && "$(stat -c '%u:%a' "$T")" == "$UID_EXPECT:700" ]] || blocked WORK_META
cleanup(){
  [[ "$T" == "$R"/kmj-x25519-disposable.* && -d "$T" && ! -L "$T" ]] || return 0
  [[ "$(stat -c '%u:%a' "$T" 2>/dev/null)" == "$UID_EXPECT:700" ]] || return 0
  /usr/bin/rm -rf --one-file-system -- "$T"
}
trap cleanup EXIT
install -m 600 "$P/$A" "$T/helper.py"
install -m 600 "$P/$C" "$T/$C"
printf '%s  %s\n' 'c72476c4be2648e3ed31457334b7e5acba56d52084e5059c932ffd4bf45fcc9c' "$T/helper.py" \
'b20e55f1de13d8bae3f6e4156dafc135002b4d73215bf3f5613359419c893f26' "$T/$C" \
| sha256sum -c - || blocked HELPER_COPY_SHA
python3 -I -B "$T/helper.py" --prepare "$T" || blocked COPY_CIPHER
[[ ! -L "$T/cipher.age" && "$(stat -c '%u:%a:%s' "$T/cipher.age")" == "$UID_EXPECT:600:442310" ]] || blocked CIPHER_META
: > "$T/key.mount"
chmod 600 "$T/key.mount"
mkdir -m 700 "$T/dbwork" "$T/dbwork/socket"

clean=(/usr/bin/env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin HOME=/home/info USER=info LOGNAME=info LC_ALL=C LANG=C)
base=(/usr/bin/bwrap --unshare-all --die-with-parent --new-session --cap-drop ALL
 --ro-bind / / --proc /proc --dev /dev --tmpfs /run --tmpfs /tmp --tmpfs /var/tmp
 --tmpfs "$HOME" --bind "$T" "$T")
keyzone=("${base[@]}" --ro-bind "$KEY" "$T/key.mount")
if ! "${clean[@]}" "${keyzone[@]}" /bin/bash -c \
 '[[ -s "$1" && -r "$1" && ! -e "$2" ]]' _ "$T/key.mount" "$HOME/.ssh" >/dev/null 2>&1; then
 blocked KEY_SANDBOX
fi
if ! "${clean[@]}" "${base[@]}" /bin/bash -c \
 '[[ -f "$1" && ! -s "$1" && ! -e "$2" ]]' _ "$T/key.mount" "$HOME/.ssh" >/dev/null 2>&1; then
 blocked KEYFREE_SANDBOX
fi
echo 'AGE_KEY_ISOLATION=PASS'
if ! timeout --signal=TERM --kill-after=15s 90s \
 "${clean[@]}" "${keyzone[@]}" /usr/bin/age -d -i "$T/key.mount" \
 -o "$T/bundle.tar.gz" "$T/cipher.age" >/dev/null 2>&1; then
 blocked AGE_SANDBOX_DECRYPT
fi
[[ ! -L "$T/bundle.tar.gz" && "$(stat -c '%u:%a:%h' "$T/bundle.tar.gz")" == "$UID_EXPECT:600:1" ]] || blocked BUNDLE_META
[[ ! -s "$T/key.mount" ]] || blocked KEY_PLACEHOLDER
rm -- "$T/key.mount"
echo 'ISOLATED_X25519_DECRYPT=PASS'
if ! timeout --signal=TERM --kill-after=15s 120s \
 "${clean[@]}" "${base[@]}" /usr/bin/python3 -I -B "$T/helper.py" --extract "$T"; then
 blocked PGDMP_EXTRACTION
fi
[[ ! -L "$T/database.dump" && "$(stat -c '%u:%a:%h' "$T/database.dump")" == "$UID_EXPECT:600:1" ]] || blocked PGDMP_META
[[ ! -L "$T/storage.tar.gz" && "$(stat -c '%u:%a:%h' "$T/storage.tar.gz")" == "$UID_EXPECT:600:1" ]] || blocked VERIFIED_STORAGE_COPY_META
echo 'FRESH_PGDMP_AND_STORAGE_MANIFEST=PASS'

cat > "$T/run-db.sh" <<'INNER'
#!/bin/bash -p
set -Eeuo pipefail
BIN=$1; WORK=$2; PORT=$3; DUMP=$4
stage(){ printf 'STAGE=%s\n' "$1" > "$WORK/stage"; }
stopdb(){ "$BIN/pg_ctl" -D "$WORK/pgdata" -m immediate -w stop >/dev/null 2>&1 || :; }
trap stopdb EXIT
stage INITDB
"$BIN/initdb" -D "$WORK/pgdata" -U kmj_restore_drill --auth-local=trust --auth-host=reject --no-instructions > "$WORK/init.log" 2>&1
stage START
"$BIN/pg_ctl" -D "$WORK/pgdata" -l "$WORK/pg.log" -o "-c listen_addresses='' -c unix_socket_directories='$WORK/socket' -c unix_socket_permissions=0700 -c port=$PORT" -w start >/dev/null 2>&1
[[ -S "$WORK/socket/.s.PGSQL.$PORT" ]]
stage CREATE
"$BIN/createdb" -h "$WORK/socket" -p "$PORT" -U kmj_restore_drill recovered_kmj > "$WORK/create.log" 2>&1
stage RESTORE
"$BIN/pg_restore" --exit-on-error --no-owner --no-acl -h "$WORK/socket" -p "$PORT" \
 -U kmj_restore_drill -d recovered_kmj "$DUMP" > "$WORK/restore.log" 2>&1
stage SCHEMA
TABLES=$("$BIN/psql" -X -A -t -h "$WORK/socket" -p "$PORT" -U kmj_restore_drill -d recovered_kmj -v ON_ERROR_STOP=1 \
 -c "select count(*) from pg_catalog.pg_class where relkind in ('r','p') and relnamespace in (select oid from pg_catalog.pg_namespace where nspname='public')" 2>/dev/null)
[[ "$TABLES" =~ ^[0-9]+$ && "$TABLES" -ge 1 && "$TABLES" -le 100000 ]]
USERS=$("$BIN/psql" -X -A -t -h "$WORK/socket" -p "$PORT" -U kmj_restore_drill -d recovered_kmj -v ON_ERROR_STOP=1 \
 -c "select (to_regclass('public.users') is not null)::int" 2>/dev/null)
[[ "$USERS" == 0 || "$USERS" == 1 ]]
printf 'TABLES=%s\nUSERS=%s\n' "$TABLES" "$USERS" > "$WORK/receipt"
stage DONE
INNER
chmod 700 "$T/run-db.sh"
db=(/usr/bin/bwrap --unshare-all --die-with-parent --new-session --cap-drop ALL
 --ro-bind / / --proc /proc --dev /dev --tmpfs /run --tmpfs /tmp --tmpfs /var/tmp
 --tmpfs "$HOME" --ro-bind "$T" "$T" --bind "$T/dbwork" "$T/dbwork")
if ! "${clean[@]}" "${db[@]}" /bin/bash -c \
 '[[ -r "$1" && ! -w "$1" && -w "$2" && ! -e "$3" ]] && touch "$2/.probe" && rm -- "$2/.probe"' \
 _ "$T/database.dump" "$T/dbwork" "$HOME/.local/share/kmj-recovery/google-vps-20261019.agekey" >/dev/null 2>&1; then
 blocked PG_KEYFREE_BOUNDARY
fi
echo 'POSTGRES_SANDBOX_PREFLIGHT=PASS'
if ! timeout --signal=TERM --kill-after=20s 600s \
 "${clean[@]}" "${db[@]}" /bin/bash -p "$T/run-db.sh" \
 "$PGBIN" "$T/dbwork" 55479 "$T/database.dump" >/dev/null 2>&1; then
 STAGE=$(sed -n 's/^STAGE=\([A-Z_]*\)$/\1/p' "$T/dbwork/stage" 2>/dev/null | tail -1)
 [[ "$STAGE" =~ ^[A-Z_]{3,64}$ ]] || STAGE=SANDBOX
 printf 'RESTORE_FAILED_STAGE=%s\n' "$STAGE"
 blocked PG_RESTORE_FAILED
fi
[[ "$(cat "$T/dbwork/stage" 2>/dev/null)" == STAGE=DONE ]] || blocked FINAL_RECEIPT
TABLES=$(sed -n 's/^TABLES=\([0-9]\+\)$/\1/p' "$T/dbwork/receipt" 2>/dev/null)
USERS=$(sed -n 's/^USERS=\([01]\)$/\1/p' "$T/dbwork/receipt" 2>/dev/null)
[[ "$TABLES" =~ ^[0-9]+$ && "$USERS" =~ ^[01]$ ]] || blocked RECEIPT_FORMAT
echo "RESTORED_PUBLIC_TABLES=$TABLES"
echo "RESTORED_USERS_TABLE=$USERS"
echo 'POSTGRES_DISPOSABLE_RESTORE=PASS'
echo 'POSTGRES_TCP_LISTENER=DISABLED'
echo 'RESTORE_NETWORK_NAMESPACE=UNSHARED'
echo 'AGE_KEY_IN_DATABASE_NAMESPACE=NO'
echo 'V3_20261117_SOURCE_HASH_MANIFEST=VERIFIED_ON_GOOGLE'
echo 'SOURCE_CONTENT_PARITY=NOT_INDEPENDENTLY_ATTESTED'
echo 'PRODUCTION_DATABASE_MODIFIED=NO'
echo 'PRODUCTION_SERVICE_MODIFIED=NO'
echo 'RESULT=V3_20261117_GOOGLE_DISPOSABLE_PG_RESTORE_PASS'
