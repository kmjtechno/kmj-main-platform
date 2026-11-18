#!/usr/bin/python3
"""Owner-reviewed optional recurring dual-local backup timer for KMJ-elite.

Source/review only. This file is NOT an installed service or approval.
Modes: --selftest (offline), --inspect (root read-only, private /run scratch),
--install (EXPLICIT owner-approved systemd installation), --disable
(EXPLICIT rollback of only the new timer; preserves backup data/files).

The existing offsite V3 service and health-check units are never edited,
restarted, stopped or disabled. The two new timer windows avoid the installed
08:50 offsite timer and are protected by V3's existing exclusive flock.
No old backups, snapshots, symlinks, approvals, keys, or databases are removed.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import tempfile

SOURCE=Path("/srv/kmj-codebridge-projects/kmj-main-platform/scripts/KMJ_OFFSITE_V3_DUAL_LOCAL_HEALTH_ONEPASS_20261117.py")
PIN="bea4fcffefd369b8200628b860a8af7971b3143662a9566b1db8c5d2607ad650"
ROOT=Path("/usr/local/libexec")
RUNNER=ROOT/"kmj-v3-dual-local-health-onepass-20261118.py"
SIDECAR=ROOT/"kmj-v3-dual-local-health-onepass-20261118.sha256"
UNITS=Path("/etc/systemd/system")
SERVICE="kmj-v3-dual-local-health.service"
TIMER="kmj-v3-dual-local-health.timer"
SERVICE_PATH=UNITS/SERVICE
TIMER_PATH=UNITS/TIMER
ORIGINAL_SERVICE="kmj-elite-offsite-backup.service"
ORIGINAL_TIMER="kmj-elite-offsite-backup.timer"
ORIGINAL_HEALTH="kmj-elite-health-check.service"
RUN_ENV={"PATH":"/usr/sbin:/usr/bin:/sbin:/bin","LC_ALL":"C","LANG":"C","HOME":"/root"}

SERVICE_TEXT="""[Unit]
Description=KMJ V3 guarded dual-local backup and original health check
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=root
Group=root
UMask=0077
ExecStartPre=/usr/bin/sha256sum --check --status /usr/local/libexec/kmj-v3-dual-local-health-onepass-20261118.sha256
ExecStart=/usr/bin/python3 -I -B /usr/local/libexec/kmj-v3-dual-local-health-onepass-20261118.py --run-once
TimeoutStartSec=3600s
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=read-only
ProtectSystem=strict
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
LockPersonality=true
ReadWritePaths=/var/backups/kmj-elite-daily /var/backups/kmj-elite-offsite-encrypted /var/backups/kmj-v3-private-stage /usr/local/libexec/kmj-offsite-dual-local-v3-certbot-20261115 /run /tmp
"""
TIMER_TEXT="""[Unit]
Description=Schedule KMJ V3 dual-local backup (two daily safe windows)

[Timer]
OnCalendar=*-*-* 03:45:00
OnCalendar=*-*-* 15:45:00
Persistent=false
RandomizedDelaySec=0
AccuracySec=2min
Unit=kmj-v3-dual-local-health.service

[Install]
WantedBy=timers.target
"""
CHECKSUM_TEXT=PIN+"  "+str(RUNNER)+"\n"

class Deny(Exception):
    pass

def host_root():
    if os.geteuid()!=0 or socket.gethostname().split(".")[0]!="KMJ-elite":
        raise Deny("OWNER_ROOT_KMJ_ELITE_REQUIRED")

def guard_dir(path):
    info=os.lstat(path)
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid!=0
            or info.st_mode&0o022):
        raise Deny("ROOT_DIRECTORY_METADATA_INVALID")

def read_exact(path, expected, *, expected_uid=None, limit=131072):
    before=os.lstat(path)
    if (not stat.S_ISREG(before.st_mode) or before.st_nlink!=1
        or before.st_mode&0o022 or not 128<=before.st_size<=limit
        or (expected_uid is not None and before.st_uid!=expected_uid)):
        raise Deny("SOURCE_METADATA_INVALID")
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        original=os.fstat(fd)
        raw=os.read(fd,limit+1)
        after=os.fstat(fd)
        finger=lambda st:(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns,st.st_mode)
        if (finger(before)!=finger(original) or finger(original)!=finger(after)
            or len(raw)!=original.st_size):
            raise Deny("SOURCE_CHANGED_DURING_READ")
    finally:
        os.close(fd)
    if hashlib.sha256(raw).hexdigest()!=expected:
        raise Deny("SOURCE_SHA_MISMATCH")
    return raw

def sysrun(args,timeout=16):
    got=subprocess.run(args,cwd="/",env=RUN_ENV,stdin=subprocess.DEVNULL,
                       stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                       check=False,timeout=timeout)
    if got.returncode!=0:
        raise Deny("FIXED_SYSTEMD_OPERATION_FAILED")
    return got.stdout.decode("ascii","strict")

def prop(unit,key):
    if unit not in (ORIGINAL_SERVICE,ORIGINAL_TIMER,ORIGINAL_HEALTH,SERVICE,TIMER):
        raise Deny("UNLISTED_UNIT")
    if key not in ("LoadState","ActiveState","UnitFileState","ExecMainStatus","Result","Type"):
        raise Deny("UNLISTED_PROPERTY")
    return sysrun(["/usr/bin/systemctl","show",unit,"--no-pager","--property="+key,"--value"]).strip()

def verify_existing_baseline():
    for parent in ("/usr","/usr/local",ROOT,"/etc","/etc/systemd",UNITS,
                   "/var","/var/backups","/run","/run/lock"):
        guard_dir(Path(parent))
    for folder in ("/var/backups/kmj-elite-daily",
                   "/var/backups/kmj-elite-offsite-encrypted",
                   "/var/backups/kmj-v3-private-stage",
                   "/usr/local/libexec/kmj-offsite-dual-local-v3-certbot-20261115"):
        guard_dir(Path(folder))
    if (prop(ORIGINAL_SERVICE,"LoadState")!="loaded"
        or prop(ORIGINAL_SERVICE,"Type")!="oneshot"
        or prop(ORIGINAL_TIMER,"LoadState")!="loaded"
        or prop(ORIGINAL_TIMER,"ActiveState")!="active"
        or prop(ORIGINAL_HEALTH,"LoadState")!="loaded"
        or prop(ORIGINAL_HEALTH,"Result")!="success"
        or prop(ORIGINAL_HEALTH,"ExecMainStatus")!="0"):
        raise Deny("ORIGINAL_BACKUP_OR_HEALTH_NOT_READY")
    if prop(SERVICE,"LoadState")!="not-found" or prop(TIMER,"LoadState")!="not-found":
        raise Deny("RECURRING_UNIT_COLLISION")
    for target in (RUNNER,SIDECAR,SERVICE_PATH,TIMER_PATH):
        if os.path.lexists(target):
            raise Deny("EXISTING_INSTALLATION_REQUIRES_OWNER_REVIEW")
    source=read_exact(SOURCE,PIN)
    return source

def pinned_runner_preflight(source):
    with tempfile.TemporaryDirectory(prefix="kmj-v3-autotimer-",dir="/run") as d:
        scratch=Path(d)
        os.chmod(scratch,0o700)
        tmp=scratch/"runner.py"
        fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o500)
        try:
            os.write(fd,source)
            os.fsync(fd)
        finally:
            os.close(fd)
        read_exact(tmp,PIN,expected_uid=0)
        for mode,marker in (("--selftest","KMJ_V3_HEALTH_ONEPASS_20261117_OFFLINE_SELFTEST=PASS"),
                            ("--audit-pins","RESULT=ROOT_PIN_AUDIT_PASS"),
                            ("--preflight","RESULT=GUARDED_ONEPASS_PREFLIGHT_PASS")):
            output=sysrun(["/usr/bin/python3","-I","-B",str(tmp),mode],timeout=50)
            if marker not in output:
                raise Deny("PINNED_RUNNER_"+mode[2:].upper().replace("-","_")+"_NOT_PASS")
    print("RUNNER_SELFTEST_AUDIT_AND_PREFLIGHT=PASS")
    print("HOST_BACKUP_TRANSFER_EXECUTED=NO")

def no_clobber_install(path,body,mode):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    try:
        os.fchmod(fd,mode)
        os.fchown(fd,0,0)
        offset=0
        while offset<len(body):
            n=os.write(fd,body[offset:])
            if n<=0:
                raise Deny("SHORT_INSTALL_WRITE")
            offset+=n
        os.fsync(fd)
    finally:
        os.close(fd)

def install():
    source=verify_existing_baseline()
    pinned_runner_preflight(source)
    created=[]
    try:
        for path,body,mode in (
            (RUNNER,source,0o600),(SIDECAR,CHECKSUM_TEXT.encode("ascii"),0o600),
            (SERVICE_PATH,SERVICE_TEXT.encode("ascii"),0o644),
            (TIMER_PATH,TIMER_TEXT.encode("ascii"),0o644)):
            no_clobber_install(path,body,mode)
            created.append(path)
        read_exact(RUNNER,PIN,expected_uid=0)
        if SIDECAR.read_bytes()!=CHECKSUM_TEXT.encode("ascii"):
            raise Deny("INSTALLED_SHA_SIDECAR_CHANGED")
        sysrun(["/usr/bin/systemd-analyze","verify",str(SERVICE_PATH),str(TIMER_PATH)],timeout=30)
        sysrun(["/usr/bin/systemctl","daemon-reload"],timeout=30)
        if prop(SERVICE,"LoadState")!="loaded" or prop(TIMER,"LoadState")!="loaded":
            raise Deny("NEW_TIMER_UNITS_NOT_LOADED")
        # Persistent=false prevents an immediate missed-run catchup.
        sysrun(["/usr/bin/systemctl","enable","--now",TIMER],timeout=40)
        if (prop(TIMER,"ActiveState")!="active"
            or prop(TIMER,"UnitFileState")!="enabled"
            or prop(SERVICE,"ActiveState")!="inactive"):
            raise Deny("NEW_TIMER_NOT_ACTIVE_OR_SERVICE_UNEXPECTED")
        print("NEW_RECURRING_TIMER=ENABLED")
        print("FIRST_SCHEDULED_DUAL_LOCAL_BACKUP=NOT_YET_VERIFIED")
        print("EXISTING_OFFSITE_SERVICE_AND_TIMER=UNCHANGED")
        print("PRODUCTION_RELEASE_AND_DB_MUTATION=NONE")
        print("RESULT=GUARDED_NEW_TIMER_INSTALLED")
        return 0
    except Exception:
        # Never delete a running new service's executable after partial start.
        try:
            sysrun(["/usr/bin/systemctl","disable","--now",TIMER],timeout=40)
        except (Deny,OSError,subprocess.TimeoutExpired):
            pass
        try:
            running=prop(SERVICE,"ActiveState") in ("active","activating")
        except (Deny,OSError,subprocess.TimeoutExpired):
            running=True
        if not running:
            for target in reversed(created):
                try:
                    if target.is_file() and not target.is_symlink():
                        target.unlink()
                except OSError:
                    pass
            try:sysrun(["/usr/bin/systemctl","daemon-reload"],timeout=30)
            except (Deny,OSError,subprocess.TimeoutExpired):pass
        raise

def inspect():
    source=verify_existing_baseline()
    pinned_runner_preflight(source)
    print("NEW_TIMER_INSTALLATION=OWNER_APPROVAL_REQUIRED")
    print("EXISTING_SERVICES_AND_PRODUCTION=UNTOUCHED")
    print("RESULT=GUARDED_NEW_TIMER_INSTALL_PREFLIGHT_PASS")

def disable():
    host_root()
    guard_dir(UNITS)
    if not all(os.path.isfile(path) and not os.path.islink(path)
               for path in (RUNNER,SIDECAR,SERVICE_PATH,TIMER_PATH)):
        raise Deny("NEW_TIMER_NOT_INSTALLED_EXACT")
    read_exact(RUNNER,PIN,expected_uid=0)
    if SERVICE_PATH.read_bytes()!=SERVICE_TEXT.encode("ascii") or TIMER_PATH.read_bytes()!=TIMER_TEXT.encode("ascii"):
        raise Deny("NEW_UNIT_CONTENT_CHANGED")
    sysrun(["/usr/bin/systemctl","disable","--now",TIMER],timeout=40)
    if prop(TIMER,"ActiveState")!="inactive":
        raise Deny("TIMER_DISABLE_UNVERIFIED")
    print("NEW_TIMER=DISABLED")
    print("EXISTING_OFFSITE_TIMER=UNCHANGED")
    print("BACKUP_FILES_AND_RUNNER=RETAINED_FOR_REVIEW")
    print("RESULT=SAFE_TIMER_DISABLE_PASS")
    return 0

def selftest():
    assert len(PIN)==64 and re.fullmatch("[0-9a-f]{64}",PIN)
    assert CHECKSUM_TEXT==PIN+"  "+str(RUNNER)+"\n"
    assert "Persistent=false" in TIMER_TEXT
    assert TIMER_TEXT.count("OnCalendar=")==2
    assert "Unit="+SERVICE in TIMER_TEXT
    assert "ExecStartPre=/usr/bin/sha256sum --check --status "+str(SIDECAR) in SERVICE_TEXT
    assert "ExecStart=/usr/bin/python3 -I -B "+str(RUNNER)+" --run-once" in SERVICE_TEXT
    assert "ProtectSystem=strict" in SERVICE_TEXT
    assert "ReadWritePaths=/var/backups/kmj-elite-daily " in SERVICE_TEXT
    assert "kmj-elite-offsite-backup.service" not in SERVICE_TEXT
    assert "kmj-elite-offsite-backup.timer" not in TIMER_TEXT
    print("KMJ_V3_RECURRING_TIMER_OFFLINE_SELFTEST=PASS")
    print("HOST_OR_SERVICE_MUTATION=NONE")
    return 0

def main():
    os.umask(0o077)
    if len(sys.argv)!=2 or sys.argv[1] not in ("--selftest","--inspect","--install","--disable"):
        print("RESULT=BLOCKED_ARGS")
        return 2
    try:
        if sys.argv[1]=="--selftest":return selftest()
        host_root()
        if sys.argv[1]=="--inspect":inspect();return 0
        if sys.argv[1]=="--install":return install()
        return disable()
    except (Deny,OSError,UnicodeError,subprocess.TimeoutExpired) as e:
        category=str(e)
        if not re.fullmatch("[A-Z0-9_]{5,100}",category):
            category=type(e).__name__.upper()
        print("BLOCKER="+category)
        print("PRODUCTION_RELEASE_AND_EXISTING_OFFSITE_UNIT_MUTATION=NONE")
        print("RESULT=BLOCKED_FAIL_CLOSED")
        return 3

if __name__=="__main__":
    raise SystemExit(main())
