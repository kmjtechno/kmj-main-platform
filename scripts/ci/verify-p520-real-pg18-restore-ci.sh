#!/usr/bin/env bash
# Actual disposable PostgreSQL18 + uploads restore using P520 Python source.
# SYNTHETIC DATA ONLY. Does not access owner P520, Google VPS or production.
set -Eeuo pipefail
umask 077
[[ "$#" == 1 && "$1" =~ ^[a-f0-9]{40}$ ]] || { echo BLOCKED_SHA_ARG; exit 2; }
[[ "$GITHUB_ACTIONS" == true && -n "$RUNNER_TEMP" && "$(id -u)" != 0 ]] || {
  echo BLOCKED_NOT_UNPRIVILEGED_GITHUB_CI; exit 2;
}
for name in git docker python3 node; do
  command -v "$name" >/dev/null || { echo BLOCKED_MISSING_DEPENDENCY;exit 2; }
done
[[ "$(git rev-parse HEAD)" == "$1" ]] || { echo BLOCKED_CHECKOUT_SHA_DRIFT;exit 2; }
base='postgres:18.6-alpine3.24@sha256:10a5c69a83035ab5239f5620d708520e8b28f5aa1f2b20143e6024532edadfb5'
tag="kmj-p520-synthetic-pg18:$1"
name="kmj-p520-synthetic-pg18-$GITHUB_RUN_ID"
tmp="$(mktemp -d "$RUNNER_TEMP/kmj-p520-pg18.XXXXXXXX")"
cleanup(){
  docker rm -fv "$name" >/dev/null 2>&1 || true
  if [[ -d "$tmp" && ! -L "$tmp" && "$tmp" == "$RUNNER_TEMP"/kmj-p520-pg18.* ]]; then
    rm -rf -- "$tmp"
  fi
}
trap cleanup EXIT
# Allowed external image/package retrieval only inside ephemeral hosted CI.
docker pull --quiet "$base" >/dev/null
docker build --pull=false --no-cache -t "$tag" \
  -f scripts/ci/Dockerfile.p520-pg18-restore-ci . >/dev/null
docker run -d --name "$name" --pull=never --network=none \
  -e POSTGRES_USER=kmj_qa -e POSTGRES_DB=kmj_source_qa \
  -e POSTGRES_PASSWORD=CI_SYNTHETIC_ONLY "$tag" >/dev/null
ready=0
for _ in $(seq 1 45); do
  if docker exec -u postgres "$name" psql -X -A -t \
    -h /var/run/postgresql -U kmj_qa -d kmj_source_qa \
    -v ON_ERROR_STOP=1 -c 'SELECT 1' 2>/dev/null | grep -qx 1; then
    ready=1;break
  fi
  sleep 1
done
[[ "$ready" == 1 ]] || { echo BLOCKED_PG_NOT_READY;exit 2; }
docker exec -u postgres "$name" psql -X -q -h /var/run/postgresql \
  -U kmj_qa -d kmj_source_qa -v ON_ERROR_STOP=1 \
  -c 'CREATE TABLE public.kmj_p520_roundtrip (id integer PRIMARY KEY, marker text NOT NULL)' \
  -c "INSERT INTO public.kmj_p520_roundtrip VALUES (1, 'CI_SYNTHETIC_NO_CUSTOMER_DATA')"
docker exec -u postgres "$name" pg_dump -h /var/run/postgresql \
  -U kmj_qa -d kmj_source_qa -Fc > "$tmp/database.dump"
[[ "$(head -c 5 "$tmp/database.dump")" == PGDMP ]] || { echo BLOCKED_BAD_PG_DUMP;exit 2; }
node --input-type=module -e '
 import {RESTORE_PY} from "./scripts/windows/P520-OFFSITE-PG-STORAGE-RESTORE-20261116.mjs";
 process.stdout.write(RESTORE_PY);
' > "$tmp/restore.py"
python3 - "$tmp" <<'PY'
from pathlib import Path
from io import BytesIO
import hashlib
import sys
import tarfile
root=Path(sys.argv[1])
data=b"KMJ synthetic recovered upload -- no customer data\n"
inner=BytesIO()
with tarfile.open(fileobj=inner,mode="w:gz") as tar:
    info=tarfile.TarInfo("storage/app/proof.txt")
    info.size=len(data)
    tar.addfile(info,BytesIO(data))
meta=("backup_kind=offsite_sanitized_local_witness\n"
      "source_local_sha256="+"a"*64+"\n"
      "target_sha=4c9d59103b99a6cfe675bb7b8961fc956eb294f0\n"
      "current_release=platform-ce6ad7dc9d89\n"
      "production_env_excluded=YES\n").encode("ascii")
files={"database.dump":(root/"database.dump").read_bytes(),
       "storage.tar.gz":inner.getvalue(),"metadata.txt":meta}
files["SHA256SUMS"]="".join(
    hashlib.sha256(value).hexdigest()+"  "+name+"\n"
    for name,value in files.items()).encode("ascii")
with tarfile.open(root/"bundle.tar.gz","w:gz") as tar:
    for name,value in files.items():
        info=tarfile.TarInfo(name)
        info.size=len(value)
        tar.addfile(info,BytesIO(value))
PY
# CI synthetic files only; read-only bind readable by Docker's postgres UID.
chmod 0755 "$tmp"
chmod 0644 "$tmp/bundle.tar.gz" "$tmp/restore.py"
# CI-only diagnosis: call the UNCHANGED embedded main() and report bounded
# exception class/reason from synthetic data without weakening production code.
cat > "$tmp/debug.py" <<'PY'
from pathlib import Path
import sys
source=Path("/recovery/restore.py")
code=compile(source.read_text("utf8"),str(source),"exec")
scope={"__name__":"kmj_ci_synthetic"}
exec(code,scope)
sys.argv=["restore.py","a"*64]
try:
    scope["main"]()
except Exception as exc:
    print("KMJ_SYNTHETIC_FAILURE_CLASS="+type(exc).__name__,file=sys.stderr)
    print("KMJ_SYNTHETIC_FAILURE_DETAIL="+str(exc)[:160],file=sys.stderr)
    sys.exit(2)
PY
chmod 0644 "$tmp/debug.py"
docker rm -fv "$name" >/dev/null
output="$(docker run --rm --pull=never --network=none --read-only \
  --cap-drop=ALL --security-opt=no-new-privileges --user=postgres \
  --pids-limit=128 --cpus=1 --memory=2048m \
  --tmpfs=/tmp:rw,nosuid,nodev,size=1024m,mode=1777 \
  --mount="type=bind,src=$tmp,dst=/recovery,readonly" \
  --entrypoint=python3 "$tag" /recovery/debug.py)"
[[ "$output" == KMJ_P520_DISPOSABLE_PG_STORAGE=PASS ]] || {
  echo BLOCKED_SYNTHETIC_RESTORE_RECEIPT; exit 2;
}
echo 'KMJ_P520_REAL_PG18_RESTORE_SYNTHETIC=PASS'
echo 'KMJ_P520_REAL_UPLOADS_SHA_PARITY_SYNTHETIC=PASS'
echo 'KMJ_P520_DISPOSABLE_NETWORK_NONE_NONROOT=PASS'
echo 'OWNER_P520_BACKUP_AND_RESTORE=NOT_EXECUTED'
echo 'OWNER_PROTECTED_APPROVAL=NOT_GRANTED'
