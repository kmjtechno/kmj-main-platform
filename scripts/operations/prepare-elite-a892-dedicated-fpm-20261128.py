#!/usr/bin/env python3
"""Prepare a dedicated, not-yet-routed a892 PHP-FPM service.

Inspect is read-only. Prepare creates only new root-owned configuration files;
it validates the standalone FPM config and systemd unit but never starts or
enables the service, reloads systemd, changes nginx, or touches production.
A separate guarded start/readback must verify the new namespace and HTTP.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import tempfile

SHA = "a892b0d5d851129a9d8ed00c1af1390da6ee584f"
APP = Path("/home/kmjstage/releases") / SHA / "apps/platform"
TARGET = APP / "storage/app"
SOURCE = Path("/home/kmjstage/shared/storage-app-b2e69decab3a")
MOUNT = "home-kmjstage-releases-"+SHA+"-apps-platform-storage-app.mount"
MOUNT_SHA = "dab5cc217ee4180f63ec3526a53c7f9a183720e2862067469be57c6905641338"
GUARD_BLOB = "ef52e58b3dcbef2a3b0db8ed3a8c58e0bcc8c053"
SERVICE = "kmj-stage-a892-fpm.service"
BASE = Path("/etc/kmj-stage-a892-fpm")
CONF = BASE / "php-fpm.conf"
GUARD = BASE / "storage-guard.php"
UNIT = Path("/etc/systemd/system") / SERVICE
RUN = Path("/run/kmj-stage-a892-fpm")
SOCKET = RUN / "fpm.sock"
ROUTE = Path("/etc/nginx/sites-available/staging.kmjtechno.com.conf")
ROUTE_SHA = "c619e1d581cc298dbf6fa616eb1835b22ad42d923e112d18265dc45b5d91fb33"
ENV = {"PATH":"/usr/sbin:/usr/bin:/sbin:/bin","LANG":"C","GIT_OPTIONAL_LOCKS":"0"}


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def call(args, timeout=30):
    p = subprocess.run(args, env=ENV, cwd="/", capture_output=True, timeout=timeout)
    need(p.returncode == 0, "COMMAND_FAILED")
    return p.stdout.decode("utf-8","strict").strip()


def chain(path):
    for p in (path,*path.parents):
        s=p.lstat()
        need(stat.S_ISDIR(s.st_mode) and s.st_uid==0 and not s.st_mode&0o022,
             "ROOT_PARENT_SCOPE")


def read(path, limit=65536):
    chain(path.parent)
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    with os.fdopen(fd,"rb") as f:
        s=os.fstat(f.fileno())
        need(stat.S_ISREG(s.st_mode) and s.st_uid==0 and s.st_nlink==1
             and not s.st_mode&0o022 and 0<s.st_size<=limit,"FILE_METADATA")
        raw=f.read(limit+1)
        fp=lambda x:(x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns,x.st_mode)
        need(len(raw)==s.st_size and fp(s)==fp(os.fstat(f.fileno()))==fp(path.lstat()),"FILE_DRIFT")
    return raw


def config_bytes():
    return (
        "[global]\n"
        "daemonize = no\n"
        f"pid = {RUN}/master.pid\n"
        "error_log = /proc/self/fd/2\n"
        "[kmjstage-a892-dedicated]\n"
        "user = kmjstage\n"
        "group = kmjstage\n"
        f"listen = {SOCKET}\n"
        "listen.owner = www-data\n"
        "listen.group = www-data\n"
        "listen.mode = 0660\n"
        "clear_env = yes\n"
        f"chdir = {APP}\n"
        "pm = ondemand\n"
        "pm.max_children = 2\n"
        "pm.process_idle_timeout = 10s\n"
        "pm.max_requests = 200\n"
        "request_terminate_timeout = 120s\n"
        "security.limit_extensions = .php\n"
        "php_admin_flag[display_errors] = off\n"
        "php_admin_flag[log_errors] = on\n"
        "php_admin_flag[expose_php] = off\n"
        f"php_admin_value[auto_prepend_file] = {GUARD}\n"
    ).encode("ascii")


def unit_bytes():
    return (
        "[Unit]\n"
        "Description=KMJ exact a892 dedicated staging PHP-FPM\n"
        f"BindsTo={MOUNT}\n"
        f"After={MOUNT}\n"
        f"RequiresMountsFor={TARGET}\n"
        "[Service]\n"
        "Type=simple\n"
        "RuntimeDirectory=kmj-stage-a892-fpm\n"
        "RuntimeDirectoryMode=0755\n"
        "PrivateMounts=yes\n"
        "ProtectSystem=full\n"
        "ProtectHome=no\n"
        "PrivateTmp=yes\n"
        "NoNewPrivileges=yes\n"
        "UMask=0027\n"
        "IPAddressDeny=any\n"
        "IPAddressAllow=localhost\n"
        f"ExecStartPre=/usr/sbin/runuser -u kmjstage -- /usr/bin/php8.4 -r 'require \"{GUARD}\"; exit(kmj_a892_storage_ready() ? 0 : 1);'\n"
        f"ExecStart=/usr/sbin/php-fpm8.4 --nodaemonize --fpm-config {CONF}\n"
        "Restart=on-failure\n"
        "RestartSec=5s\n"
        "TimeoutStartSec=30s\n"
        "TimeoutStopSec=30s\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    ).encode("ascii")


def snapshot():
    prod=Path("/home/kmjprod/current")
    stage=Path("/home/kmjstage/htdocs/staging.kmjtechno.com")
    need(prod.is_symlink() and prod.resolve(strict=True)==Path("/home/kmjprod/releases/platform-457481eb652f"),
         "PRODUCTION_POINTER")
    need(stage.is_symlink() and stage.resolve(strict=True)==Path("/home/kmjstage/releases/b2e69decab3acd861e94e11992cd8a4cff4f2b94/apps/platform"),
         "STAGING_POINTER")
    need(hashlib.sha256(read(ROUTE)).hexdigest()==ROUTE_SHA,"ROUTE_DRIFT")
    need(hashlib.sha256(read(Path("/etc/systemd/system")/MOUNT)).hexdigest()==MOUNT_SHA,"MOUNT_UNIT_PIN")
    need(call(["systemctl","is-active",MOUNT])=="active" and call(["systemctl","is-enabled",MOUNT])=="enabled","MOUNT_UNIT_STATE")
    need(not TARGET.is_symlink() and TARGET.stat().st_ino==SOURCE.stat().st_ino and
         TARGET.stat().st_dev==SOURCE.stat().st_dev,"MOUNT_IDENTITY")
    flags=call(["findmnt","--mountpoint",str(TARGET),"-n","-o","VFS-OPTIONS"])
    need({"rw","nosuid","nodev","noexec"}<=set(flags.split(",")),"HOST_MOUNT_FLAGS")
    need(read(APP/"public/build/.kmj-deploy-sha",41)==(SHA+"\n").encode(),"SOURCE_MARKER")
    release=APP.parent.parent
    git=["git","-c","safe.directory="+str(release),"-c","core.fsmonitor=false","-C",str(release)]
    need(call(git+["rev-parse","HEAD"])==SHA and
         not call(git+["status","--porcelain","--untracked-files=no"]),"TRACKED_SOURCE")
    refs=call(["git","ls-remote","--exit-code","https://github.com/kmjtechno/kmj-main-platform.git",
               "refs/heads/main","refs/heads/staging-approved"])
    need(set(refs.splitlines())=={SHA+"\trefs/heads/main",SHA+"\trefs/heads/staging-approved"},"SOURCE_DRIFT")
    approval=json.loads(read(Path("/etc/kmj-codebridge/main-platform-staging-approval.json")))
    need(approval.get("approvedSha")!=SHA,"ALREADY_APPROVED")
    need(call(["systemctl","is-active","php8.4-fpm.service"])=="active","PRODUCTION_FPM_STATE")
    pid=call(["systemctl","show","php8.4-fpm.service","-p","MainPID","--value"])
    need(pid.isdigit() and int(pid)>1,"PRODUCTION_FPM_PID")
    return pid,os.readlink(prod),os.readlink(stage)


def create(path,data):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o644)
    with os.fdopen(fd,"wb") as f:
        s=os.fstat(f.fileno())
        try:
            f.write(data)
            f.flush()
            os.fchmod(f.fileno(),0o644)
            os.fsync(f.fileno())
        except BaseException:
            t=path.lstat()
            if (s.st_dev,s.st_ino)==(t.st_dev,t.st_ino):
                path.unlink()
            raise
    return s.st_dev,s.st_ino


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--guard",type=Path,required=True)
    p.add_argument("--prepare",action="store_true")
    p.add_argument("--confirm",default="")
    a=p.parse_args()
    need(os.geteuid()==0 and socket.gethostname().split(".")[0]=="KMJ-elite","HOST_ROOT")
    need((a.prepare and a.confirm=="OWNER_PREPARE_EXACT_STAGE_DEDICATED_FPM") or
         (not a.prepare and not a.confirm),"CONFIRMATION")
    os.umask(0o022)
    guard=read(a.guard)
    need(hashlib.sha1(b"blob "+str(len(guard)).encode()+b"\0"+guard).hexdigest()==GUARD_BLOB,"GUARD_PIN")
    chain(UNIT.parent)
    chain(BASE.parent)
    for path in (BASE,UNIT,RUN,Path("/etc/systemd/system/multi-user.target.wants")/SERVICE,
                 Path("/run/systemd/system")/SERVICE,Path("/usr/lib/systemd/system")/SERVICE):
        need(not os.path.lexists(path),"CANDIDATE_SERVICE_ALREADY_EXISTS")
    before=snapshot()
    call(["/usr/bin/php8.4","-l",str(a.guard)])
    print("SOURCE_AND_HOST_MOUNT=PASS")
    print("CANDIDATE_FPM_CONFIG_SHA256="+hashlib.sha256(config_bytes()).hexdigest())
    print("CANDIDATE_FPM_UNIT_SHA256="+hashlib.sha256(unit_bytes()).hexdigest())
    print("CANDIDATE_FPM_SOCKET="+str(SOCKET))
    if not a.prepare:
        print("DEDICATED_FPM_PREPARE=INSPECT_PASS_NO_CHANGES")
        return
    created={}
    made=False
    try:
        BASE.mkdir(mode=0o755)
        made=True
        for path,data in ((GUARD,guard),(CONF,config_bytes()),(UNIT,unit_bytes())):
            created[path]=(create(path,data),data)
        call(["/usr/sbin/php-fpm8.4","-t","--fpm-config",str(CONF)])
        call(["/usr/bin/systemd-analyze","verify",str(UNIT)],timeout=60)
        need(snapshot()==before,"PRODUCTION_OR_POINTER_DRIFT")
        for path,(_,data) in created.items():
            need(read(path)==data,"CONFIG_READBACK")
    except BaseException:
        for path,(inode,data) in reversed(list(created.items())):
            s=path.lstat()
            need((s.st_dev,s.st_ino)==inode and read(path)==data,"ROLLBACK_DRIFT")
            path.unlink()
        if made:
            BASE.rmdir()
        print("DEDICATED_FPM_PREPARE_ROLLBACK=PASS_OWN_FILES_ONLY")
        raise
    print("DEDICATED_FPM_PREPARE=PASS_CONFIG_ONLY")
    print("SERVICE_STARTED=NO SERVICE_ENABLED=NO DAEMON_RELOAD=NO")
    print("PRODUCTION_FPM_RESTART=NO STAGE_ROUTE_CHANGED=NO")
    print("RUNTIME_NAMESPACE_AND_HTTP=NOT_VERIFIED")


if __name__=="__main__":
    try:
        main()
    except (OSError,ValueError,subprocess.SubprocessError) as e:
        print("DEDICATED_FPM_PREPARE=BLOCKED_"+(str(e) if isinstance(e,ValueError)
              and re.fullmatch(r"[A-Z_]+",str(e)) else type(e).__name__))
        raise SystemExit(2)
