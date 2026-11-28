#!/usr/bin/env python3
"""Exact, not-yet-serving candidate storage + source attestation transaction.

No production service restart, route, database, approval or release pointer write.
Requires the exact previously reviewed helpers. On caught failure restores only
its own files, mount unit and original symlink. A crash/power loss requires manual
review of the preserved journal and root backup; not an atomic boot transaction.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import socket
import stat
import tempfile

PINS = {
    "attest":"a7864002f10915cdb2d7f022200f9514242912d4",
    "repair":"9cc17c0c5db18a7b371461820ea4fb06a44dc15e",
    "builder":"654525519ee4b21c03f41a86da26fcf9f357d6dd",
    "rehearsal":"8ce2172ccb363cefe88e6add8b05cb2a077381b4",
    "plan":"6ab70f19e69f96cc1c21b0b89f172ff1fd1486fc",
}
UNIT_SHA = "dab5cc217ee4180f63ec3526a53c7f9a183720e2862067469be57c6905641338"
BASELINE_NGINX = "c619e1d581cc298dbf6fa616eb1835b22ad42d923e112d18265dc45b5d91fb33"


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def load(path, pin):
    for parent in path.parents:
        s = parent.lstat()
        need(stat.S_ISDIR(s.st_mode) and s.st_uid==0 and not s.st_mode&0o022,"DEPENDENCY_PARENT")
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    with os.fdopen(fd,"rb") as f:
        s=os.fstat(f.fileno())
        need(stat.S_ISREG(s.st_mode) and s.st_uid==0 and s.st_nlink==1 and
             not s.st_mode&0o022 and 0<s.st_size<=65536,"DEPENDENCY_METADATA")
        raw=f.read(65537)
        t=os.fstat(f.fileno())
        fp=lambda x:(x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns)
        need(len(raw)==s.st_size and fp(s)==fp(t)==fp(path.lstat()) and
             hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()==pin,
             "DEPENDENCY_PIN")
    scope={"__name__":"pinned_dependency","__file__":str(path)}
    exec(compile(raw,str(path),"exec"),scope)
    return scope


def create(path, raw, mode):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o400)
    with os.fdopen(fd,"wb") as f:
        s=os.fstat(f.fileno())
        try:
            f.write(raw)
            f.flush()
            os.fchmod(f.fileno(),mode)
            os.fsync(f.fileno())
        except BaseException:
            if (path.lstat().st_dev,path.lstat().st_ino)==(s.st_dev,s.st_ino):
                path.unlink()
            raise
    return s.st_dev,s.st_ino


def identity(path):
    s=path.stat()
    return s.st_dev,s.st_ino


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in PINS:
        p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--apply",action="store_true")
    p.add_argument("--confirm",default="")
    a=p.parse_args()
    need(os.geteuid()==0 and socket.gethostname().split(".")[0]=="KMJ-elite","HOST_ROOT")
    need((a.apply and a.confirm=="OWNER_INSTALL_EXACT_STAGE_STORAGE_ATTESTATION") or
         (not a.apply and not a.confirm),"CONFIRMATION")
    os.umask(0o077)
    d={k:load(getattr(a,k),v) for k,v in PINS.items()}
    r,b,t,m,h=(d[k] for k in ("repair","builder","rehearsal","plan","attest"))
    app, target, source=t["APP"],t["APP_STORAGE"],t["SHARED"]
    view, marker, seal=t["VIEWS_IGNORE"],h["MARKER"],h["SEAL"]
    lockpath=h["LOCK"]
    command=r["command"]
    def system(*args):
        return command(["/usr/bin/systemctl",*args],timeout=60).decode().strip()
    def pointers():
        need(b["exact_link"](m["STAGE"],m["STAGE_OLD"]) and
             b["exact_link"](m["PROD"],m["PROD_OLD"]),"POINTER_DRIFT")
        raw=r["read_file"](Path("/etc/nginx/sites-available/staging.kmjtechno.com.conf"),0,65536)[0]
        need(hashlib.sha256(raw).hexdigest()==BASELINE_NGINX,"NGINX_DRIFT")
        refs=command(["/usr/bin/git","ls-remote","--exit-code",r["REMOTE"],
                      "refs/heads/main","refs/heads/staging-approved"],timeout=30)
        need(set(refs.decode().splitlines())==
             {t["SHA"]+"\trefs/heads/main",t["SHA"]+"\trefs/heads/staging-approved"},"SOURCE_DRIFT")
        need(json.loads(r["read_file"](r["APPROVAL"],0,65536)[0]).get("approvedSha")!=t["SHA"],
             "CANDIDATE_ALREADY_APPROVED")
        need(hashlib.sha256(b["protected_root_file"](b["RUNNER"])).hexdigest()==r["RUNNER_SHA"],
             "RUNNER_DRIFT")
    def mount_identity():
        need(not target.is_symlink() and identity(target)==identity(source),"MOUNT_IDENTITY")
        out=command(["/usr/bin/findmnt","--json","--mountpoint",str(target),"-o","TARGET,VFS-OPTIONS"])
        rows=json.loads(out)["filesystems"]
        need(len(rows)==1 and rows[0]["target"]==str(target) and
             {"rw","nosuid","nodev","noexec"}<=set(rows[0]["vfs-options"].split(",")),
             "MOUNT_OPTIONS")
        need((target/"private/product-artwork").resolve(strict=True)==t["ARTWORK"],"ARTWORK_SCOPE")
    def fpm_visibility():
        pid=system("show","php8.4-fpm.service","-p","MainPID","--value")
        need(pid.isdigit() and int(pid)>1,"FPM_PID")
        got=command(["/usr/bin/nsenter","--target",pid,"--mount","--",
                     "/usr/bin/stat","-Lc","%d:%i",str(target)]).decode().strip()
        x,y=identity(source)
        need(got==f"{x}:{y}","FPM_MOUNT_NAMESPACE")
    r["protected_dir"](lockpath.parent)
    fd=os.open(lockpath,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    with os.fdopen(fd,"rb") as lock:
        s=os.fstat(lock.fileno())
        need(stat.S_ISREG(s.st_mode) and s.st_uid==0 and s.st_nlink==1 and
             stat.S_IMODE(s.st_mode)==0o600 and identity(lockpath)==(s.st_dev,s.st_ino),"LOCK_SCOPE")
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        need(system("show","kmj-main-platform-staging-deploy.service","-p","ActiveState","--value")=="inactive",
             "STAGE_UNIT_BUSY")
        r["guard"](b)
        pointers()
        old=r["read_file"](seal,0,65)[0]
        need(re.fullmatch(rb"[a-f0-9]{64}\n?",old) and b["seal_sha"](app)==old.decode().strip(),"ORIGINAL_SEAL")
        files=t["baseline"]()
        need(not os.path.lexists(marker),"MARKER_EXISTS")
        need(b"HEALTH_OK\n" in r["php"](r["PHP_HEALTH"]),"HEALTH")
        name=m["cmd"](["/usr/bin/systemd-escape","--path","--suffix=mount",str(target)])
        unit=Path("/etc/systemd/system")/name
        enabled=Path("/etc/systemd/system/multi-user.target.wants")/name
        unitraw=m["unit_bytes"]()
        need(hashlib.sha256(unitraw).hexdigest()==UNIT_SHA,"UNIT_PIN")
        # Reuse exact read-only planner preconditions.
        m["main"]()
        need(not os.path.lexists(unit) and not os.path.lexists(enabled),"UNIT_EXISTS")
        print("ORIGINAL_SEAL=PASS TRACKED_DELETIONS_EXACT=PASS",flush=True)
        if not a.apply:
            print("STORAGE_ATTESTATION_INSTALL=DRY_RUN_NO_CHANGES")
            return
        backup=Path(tempfile.mkdtemp(prefix="kmj-stage-storage-attestation-",dir="/root"))
        create(backup/"original.sha256",old,0o600)
        create(backup/"original-link.txt",(os.readlink(target)+"\n").encode(),0o600)
        r["sync_dir"](backup)
        saved=target.parent/("app.before-bind-"+backup.name)
        need(not os.path.lexists(saved),"BACKUP_LINK_EXISTS")
        create(backup/"layout.json",json.dumps({"saved_link":str(saved),"mountpoint":str(target),
               "unit":str(unit),"enabled_link":str(enabled),"marker":str(marker),
               "view_placeholder":str(view),"old_seal":old.decode().strip()}).encode()+b"\n",0o600)
        r["sync_dir"](backup)
        print("RECOVERY_BACKUP="+str(backup),flush=True)
        created={}
        new=None
        renamed=False
        made_dir=False
        try:
            os.rename(target,saved)
            renamed=True
            target.mkdir(mode=0o000)
            made_dir=True
            r["sync_dir"](target.parent)
            created[unit]=create(unit,unitraw,0o644)
            r["sync_dir"](unit.parent)
            system("daemon-reload")
            system("start",name)
            mount_identity()
            system("enable",name)
            need(enabled.is_symlink() and enabled.resolve(strict=True)==unit,"ENABLE_READBACK")
            need(system("is-enabled",name)=="enabled" and system("is-active",name)=="active","MOUNT_UNIT_STATE")
            fpm_visibility()
            need(b["seal_sha"](app)==old.decode().strip(),"UNCHANGED_SEAL_BEFORE_PLACEHOLDERS")
            created[view]=create(view,files[str(view.relative_to(t["RELEASE"]))],0o444)
            created[marker]=create(marker,(t["SHA"]+"\n").encode(),0o444)
            r["sync_dir"](view.parent)
            r["sync_dir"](marker.parent)
            h["tracked_clean"](r)
            pointers()
            mount_identity()
            need(b"HEALTH_OK\n" in r["php"](r["PHP_HEALTH"]),"FINAL_HEALTH")
            new=(b["seal_sha"](app)+"\n").encode()
            r["replace_seal"](old,new)
            need(r["read_file"](seal,0,65)[0]==new and b["seal_sha"](app)==new.decode().strip(),"FINAL_SEAL")
            h["tracked_clean"](r)
            pointers()
            mount_identity()
            fpm_visibility()
        except BaseException:
            # Fail closed; never unmount a different source or recursively delete.
            current=r["read_file"](seal,0,65)[0]
            need(current in (old,new),"ROLLBACK_SEAL_DRIFT")
            for path in (marker,view):
                if path in created:
                    h["remove_own"](path,created[path])
                    r["sync_dir"](path.parent)
            if unit in created:
                need(identity(unit)==created[unit] and unit.read_bytes()==unitraw,"ROLLBACK_UNIT_DRIFT")
                if os.path.lexists(enabled):
                    need(enabled.is_symlink() and enabled.resolve(strict=True)==unit,"ROLLBACK_ENABLE_DRIFT")
                    system("disable",name)
                if os.path.ismount(target) or identity(target)==identity(source):
                    need(identity(target)==identity(source),"ROLLBACK_MOUNT_DRIFT")
                    system("stop",name)
                need(not os.path.ismount(target) and identity(target)!=identity(source),"ROLLBACK_STILL_MOUNTED")
                h["remove_own"](unit,created[unit])
                system("daemon-reload")
            if made_dir:
                need(not os.path.ismount(target) and not target.is_symlink() and
                     identity(target)!=identity(source),"ROLLBACK_TARGET_SCOPE")
                target.rmdir()
            if renamed:
                need(not os.path.lexists(target) and saved.is_symlink() and
                     saved.resolve(strict=True)==source,"ROLLBACK_LINK_SCOPE")
                os.rename(saved,target)
            if current!=old:
                r["replace_seal"](current,old)
            need(b["seal_sha"](app)==old.decode().strip(),"ROLLBACK_ORIGINAL_SEAL")
            print("STORAGE_ATTESTATION_ROLLBACK=PASS",flush=True)
            raise
        print("PERSISTENT_MOUNT=ACTIVE_ENABLED")
        print("FPM_MOUNT_VISIBILITY=PASS")
        print("TRACKED_SOURCE=PASS")
        print("DEPLOY_ATTESTATION=PASS")
        print("CANDIDATE_SECURITY_SEAL=REGENERATED_VERIFIED")
        print("BOOT_RESTART_TEST=NOT_EXECUTED")
        print("CANDIDATE_RUNTIME_MOUNT_GUARD=STILL_REQUIRED")
        print("STAGING_POINTER=UNCHANGED PRODUCTION_POINTER=UNCHANGED APPROVAL_UPDATED=NO")
        print("STORAGE_ATTESTATION_INSTALL=PASS")


if __name__=="__main__":
    def interrupted(_s,_f):
        raise InterruptedError("SIGNAL")
    signal.signal(signal.SIGHUP,interrupted)
    signal.signal(signal.SIGTERM,interrupted)
    try:
        main()
    except Exception as e:
        print("STORAGE_ATTESTATION_INSTALL=BLOCKED_"+(str(e) if isinstance(e,ValueError)
              and re.fullmatch(r"[A-Z_]+",str(e)) else type(e).__name__))
        raise SystemExit(2)
