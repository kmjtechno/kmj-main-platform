#!/usr/bin/env python3
"""KMJ-elite: independent SHA-pinned archive restore into disposable local PG.
No production DB connection, no backup overwrite, no release/DNS mutation.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile

SHA = "69acb9b3f738e5edcc6ea85c3c76729eaa1b5b62"
OLD = "platform-8070dad72c55"
BASE = Path("/home/kmjprod")
LIVE = BASE / "current"
CANDIDATE = BASE / "releases" / ("platform-" + SHA[:12])
B = Path("/var/backups/kmj-platform")
ARCHIVE = B / ("pre-deploy-" + SHA[:12] + ".tar.gz")
WITNESS = B / ("pre-deploy-" + SHA[:12] + ".json")
LOCK = Path("/run/lock/kmj-main-platform-production-release.lock")
EXPECTED = {"database.dump", "storage.tar.gz", "metadata.txt", "SHA256SUMS"}
SECRET_ENV_NAMES = {"DB_URL", "DATABASE_URL", "BACKUP_DATABASE_URL"}
ENV = {k: v for k, v in os.environ.items() if not k.startswith("PG") and k not in SECRET_ENV_NAMES}

def fail(s):
    raise RuntimeError(s)

def sha256_file(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda:f.read(1048576),b""):
            h.update(part)
    return h.hexdigest()

def private_file(p):
    st=p.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_nlink!=1 or st.st_uid!=0 or st.st_mode & 0o077:
        fail("BACKUP_NOT_ROOT_ONLY")
    return st

def run(args, allow_output=False):
    proc=subprocess.run(args,capture_output=True,text=True,timeout=1200,env=ENV)
    if proc.returncode:
        fail("ISOLATED_COMMAND_FAILED")
    return proc.stdout.strip() if allow_output else ""

def pg_bin():
    choices=[]
    for path in Path("/usr/lib/postgresql").glob("*/bin"):
        if all((path/x).is_file() for x in ("initdb","pg_ctl","psql","pg_restore","createdb")):
            choices.append(path)
    if not choices: fail("DISPOSABLE_POSTGRES_TOOLS_MISSING")
    return sorted(choices, key=lambda x:int(x.parent.name) if x.parent.name.isdigit() else 0)[-1]

def validate_and_extract(private, pg):
    private_file(ARCHIVE)
    stw=private_file(WITNESS)
    if stw.st_size>4096: fail("WITNESS_TOO_LARGE")
    witness=json.loads(WITNESS.read_text("utf-8"))
    if not isinstance(witness,dict) or set(witness)!={"approvedSha","currentRelease","backupSha256"}:
        fail("WITNESS_SCHEMA")
    if witness["approvedSha"]!=SHA or witness["currentRelease"]!=OLD:
        fail("WITNESS_WRONG_RELEASE")
    if sha256_file(ARCHIVE)!=witness["backupSha256"]:
        fail("BACKUP_SHA256_MISMATCH")
    with tarfile.open(ARCHIVE, "r:gz") as bundle:
        members=bundle.getmembers()
        if len(members)!=4 or {m.name for m in members}!=EXPECTED:
            fail("OUTER_ARCHIVE_MEMBERS")
        if any(not m.isfile() or m.size<=0 for m in members):
            fail("OUTER_ARCHIVE_UNSAFE")
        files={}
        for m in members:
            source=bundle.extractfile(m)
            if source is None:fail("OUTER_READ")
            if m.name in ("metadata.txt","SHA256SUMS"):
                if m.size>16384:fail("METADATA_TOO_LARGE")
                files[m.name]=source.read()
            else:
                dest=(private / "storage.tar.gz") if m.name=="storage.tar.gz" else (pg/"database.dump")
                with source, dest.open("xb") as out:
                    shutil.copyfileobj(source,out,1048576)
                os.chmod(dest,0o600)
                files[m.name]=dest
        meta=files["metadata.txt"].decode("utf-8").splitlines()
        if f"approved_sha={SHA}" not in meta or f"current_release={OLD}" not in meta:
            fail("ARCHIVED_RELEASE_METADATA")
        manifest=files["SHA256SUMS"].decode("ascii").splitlines()
        if len(manifest)!=3:fail("MANIFEST_LENGTH")
        seen=set()
        for row in manifest:
            match=re.fullmatch(r"([a-f0-9]{64})  (database\.dump|storage\.tar\.gz|metadata\.txt)",row)
            if match is None:fail("MANIFEST_FORMAT")
            digest,name=match.groups()
            if name in seen:fail("DUPLICATE_MANIFEST_NAME")
            seen.add(name)
            actual=(hashlib.sha256(files[name]).hexdigest() if name=="metadata.txt"
                    else sha256_file(files[name]))
            if actual!=digest:fail("ARCHIVE_COMPONENT_HASH_MISMATCH")
        if seen!=EXPECTED-{"SHA256SUMS"}:fail("INCOMPLETE_MANIFEST")
    # Validate, do not extract production .env or copy it to offsite.
    found_storage=False
    with tarfile.open(private/"storage.tar.gz","r:gz") as inner:
        count=0
        for m in inner:
            count+=1
            if count>100000 or not (m.isfile() or m.isdir()):
                fail("STORAGE_ARCHIVE_UNSAFE")
            raw=m.name.rstrip("/")
            norm=PurePosixPath(raw)
            if not raw or raw!=norm.as_posix() or norm.is_absolute() or ".." in norm.parts or "\\" in raw:
                fail("STORAGE_UNSAFE_PATH")
            if raw=="storage/app" or raw.startswith("storage/app/"):
                found_storage=True
            elif raw!=".env":
                fail("STORAGE_UNEXPECTED_ENTRY")
    if not found_storage:fail("STORAGE_APP_NOT_PRESENT")
    user=pwd.getpwnam("kmjprod")
    os.chown(pg/"database.dump",user.pw_uid,user.pw_gid)
    os.chmod(pg/"database.dump",0o600)
    print("EXACT_SHA_BACKUP=PASS",flush=True)
    print("ALL_BACKUP_COMPONENT_HASHES=PASS",flush=True)
    print("STORAGE_ARCHIVE_STRUCTURE=PASS",flush=True)

def main():
    if sys.argv[1:]!=["--restore"]:
        fail("EXPLICIT_RESTORE_FLAG_REQUIRED")
    if os.geteuid()!=0 or os.uname().nodename.split(".")[0]!="KMJ-elite":
        fail("WRONG_OPERATOR_OR_HOST")
    if not LIVE.is_symlink() or LIVE.resolve()!=BASE/"releases"/OLD:
        fail("PRODUCTION_POINTER_MISMATCH")
    if CANDIDATE.is_symlink() or not (CANDIDATE/".git").is_dir():
        fail("CANDIDATE_MISSING")
    head=run(["runuser","-u","kmjprod","--","git","-C",str(CANDIDATE),"rev-parse","HEAD"],True)
    dirty=run(["runuser","-u","kmjprod","--","git","-C",str(CANDIDATE),
               "status","--porcelain","--untracked-files=normal"],True)
    if head!=SHA or dirty:fail("CANDIDATE_NOT_EXACT_CLEAN")
    private_file(ARCHIVE)
    private_file(WITNESS)
    if shutil.disk_usage(BASE).free < max(4*1024**3,ARCHIVE.stat().st_size*3+1024**3):
        fail("RESTORE_DISK_CAPACITY")
    if not BASE.is_dir() or BASE.is_symlink():fail("SCRATCH_PARENT_UNSAFE")
    pg=pg_bin()
    lockfd=os.open(LOCK,os.O_CREAT|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    tmp=None
    started=False
    try:
        fcntl.flock(lockfd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        tmp=Path(tempfile.mkdtemp(prefix=".kmj-69ac-isolated-restore-",dir=BASE))
        user=pwd.getpwnam("kmjprod")
        os.chown(tmp,0,user.pw_gid)
        os.chmod(tmp,0o710)
        private=tmp/"private"
        private.mkdir(mode=0o700)
        pgdir=tmp/"pg"
        pgdir.mkdir(mode=0o700)
        os.chown(pgdir,user.pw_uid,user.pw_gid)
        sock=pgdir/"socket"
        sock.mkdir(mode=0o700)
        os.chown(sock,user.pw_uid,user.pw_gid)
        validate_and_extract(private,pgdir)
        data=pgdir/"cluster"
        # Startup is strictly no-TCP; unique private Unix socket path.
        run(["runuser","-u","kmjprod","--",str(pg/"initdb"),
             "-D",str(data),"-U","kmj_restore_drill",
             "--auth-local=trust","--auth-host=reject","--no-instructions"])
        flags=f"-c listen_addresses='' -c unix_socket_directories='{sock}' -c unix_socket_permissions=0700 -c port=55479"
        run(["runuser","-u","kmjprod","--",str(pg/"pg_ctl"),"-D",str(data),
             "-l",str(pgdir/"server.log"),"-o",flags,"-w","start"])
        started=True
        if not (sock/".s.PGSQL.55479").is_socket():
            fail("PRIVATE_SOCKET_MISSING")
        run(["runuser","-u","kmjprod","--",str(pg/"createdb"),
             "-h",str(sock),"-p","55479","-U","kmj_restore_drill","kmj_recovered"])
        run(["runuser","-u","kmjprod","--",str(pg/"pg_restore"),"--exit-on-error",
             "--no-owner","--no-acl","-h",str(sock),"-p","55479",
             "-U","kmj_restore_drill","-d","kmj_recovered",str(pgdir/"database.dump")])
        schema=run(["runuser","-u","kmjprod","--",str(pg/"psql"),
              "-X","-A","-t","-h",str(sock),"-p","55479",
              "-U","kmj_restore_drill","-d","kmj_recovered",
              "-v","ON_ERROR_STOP=1","-c",
              "select (to_regclass('public.users') is not null and to_regclass('public.organizations') is not null and to_regclass('public.entitlements') is not null)::int"],True)
        if schema!="1":fail("RESTORED_SCHEMA_INCOMPLETE")
        print("INDEPENDENT_LOCAL_POSTGRES_RESTORE=PASS")
        print("RESTORED_APP_SCHEMA=PASS")
        run(["runuser","-u","kmjprod","--",str(pg/"pg_ctl"),
             "-D",str(data),"-m","immediate","-w","stop"])
        started=False
        if not LIVE.is_symlink() or LIVE.resolve()!=BASE/"releases"/OLD:
            fail("PRODUCTION_POINTER_CHANGED")
        print("PRODUCTION_DB_MODIFIED=NO")
        print("PRODUCTION_RELEASE=UNCHANGED")
        print("OFFSITE_INDEPENDENT_RESTORE=NOT_VERIFIED")
        print("OWNER_AUTHENTICATED_QA=NOT_VERIFIED")
        print("PRODUCTION_ACTIVATION=NOT_AUTHORIZED")
    finally:
        if started and tmp is not None:
            subprocess.run(["runuser","-u","kmjprod","--",str(pg/"pg_ctl"),"-D",str(tmp/"pg/cluster"),
                            "-m","immediate","-w","stop"],capture_output=True,env=ENV,timeout=45)
        if tmp is not None and str(tmp).startswith("/home/kmjprod/.kmj-69ac-isolated-restore-") and not tmp.is_symlink():
            shutil.rmtree(tmp)
        os.close(lockfd)

if __name__=="__main__":
    try: main()
    except Exception as exc:
        code=str(exc)
        if not re.fullmatch(r"[A-Z0-9_]+",code):code="ISOLATED_RESTORE_FAILED"
        print("KMJ_RESTORE_ONLY=BLOCKED_"+code)
        print("PRODUCTION_ACTIVATION=NOT_ATTEMPTED")
        sys.exit(2)
