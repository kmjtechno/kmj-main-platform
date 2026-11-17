#!/usr/bin/env python3
"""Owner-gated V2 -> DNS-aware V3 offsite continuity migration (KMJ-elite).

Only fixed --inspect (no mutation) and --apply (one versioned migration + one
backup start). Pins known V2/V3+transport source identities, original SSH
ED25519 host key, recipient and new GCE IPv4; never trusts a scanned new key.
Does not touch prod DB, release, SSH identities, Cloudflare or historical ciphers.
"""
from __future__ import annotations
import base64
import hashlib
import os
from pathlib import Path
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile

UNIT="kmj-elite-offsite-backup.service"
TIMER="kmj-elite-offsite-backup.timer"
SRCROOT=Path("/srv/kmj-codebridge-projects/kmj-main-platform/scripts")
LIBEXEC=Path("/usr/local/libexec")
V2=LIBEXEC/"kmj-offsite-fresh-x25519-v2-20261112.py"
V2PARENT=LIBEXEC/"KMJ_OFFSITE_SFTP_31LINE_GUARDED_REPAIR_20261111.py"
V3=LIBEXEC/"kmj-offsite-fresh-x25519-v3-20261112.py"
V3PARENT=LIBEXEC/"KMJ_OFFSITE_SFTP_DNS_PINNED_V2_20261112.py"
SOURCES=(
    ("KMJ_OFFSITE_FRESH_X25519_SFTP_V3_20261112.py",
     "b594d46d2dc2dd8dec3feaea829934c34b72bde45cb836fe23d3066a9eb5f880"),
    ("KMJ_OFFSITE_SFTP_DNS_PINNED_V2_20261112.py",
     "17d99cb2ba2d0fd9a889a4f458f3a72985296a30cef040a58f0cedbf3e41fc41"),
    ("test_KMJ_OFFSITE_FRESH_X25519_SFTP_V3_20261112.py",
     "7eca739c5c4c8dc8bd2e20c307f3ef1d1dc73aab85baf8e732ebc97523e8767f"),
)
PINNED_V2="fb6ec4a4c5f0189562d35141765dcfcea84bc1cec3d8f4b79362e33d884b281e"
PINNED_V2_PARENT="3535f47c7cb49924d929978993553359f3f16320c34d11bd251de3fe1936d37f"
DROPIN=Path("/etc/systemd/system/kmj-elite-offsite-backup.service.d/97-kmj-offsite-fresh-x25519-20261112.conf")
OLD_DROPIN=("[Service]\nExecStart=\n"
            "ExecStart=/usr/bin/python3 -I -B "+str(V2)+" --scheduled-run\n"
            "TimeoutStartSec=1800s\nUMask=0077\n").encode("ascii")
NEW_DROPIN=("[Service]\nExecStart=\n"
            "ExecStart=/usr/bin/python3 -I -B "+str(V3)+" --scheduled-run\n"
            "TimeoutStartSec=1800s\nUMask=0077\n").encode("ascii")
EXPECTED_IP="34.132.7.161"
HOST="offsite.kmjtechno.com"
HOSTKEY_PIN="SHA256:9ibmOwHchvHmaLTDNv8Osm0IIepfZNnQY+BMF7CuJWU"
ENV={"PATH":"/usr/sbin:/usr/bin:/sbin:/bin","LANG":"C","LC_ALL":"C","HOME":"/root"}
PROPS=("Id","LoadState","Type","User","ActiveState","Result","ExecMainStatus","InvocationID","ExecStart","DropInPaths")
TIMER_PROPS=("Id","LoadState","ActiveState","Unit","UnitFileState")
MAX_OUTPUT=262144
class Guard(Exception):pass

def run(argv,timeout=15):
    try:
        r=subprocess.run(argv,env=ENV,cwd="/",stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                         check=False,timeout=timeout)
    except (OSError,subprocess.TimeoutExpired):
        raise Guard("FIXED_COMMAND_UNAVAILABLE") from None
    if len(r.stdout)>MAX_OUTPUT:raise Guard("OUTPUT_OVERSIZE")
    return r

def safe_read(path,sha=None,*,require_root=False,mode=None,minimum=1,maximum=131072):
    s=os.lstat(path)
    if (not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or
        s.st_mode&0o022 or not minimum<=s.st_size<=maximum or
        (require_root and s.st_uid!=0) or
        (mode is not None and stat.S_IMODE(s.st_mode)!=mode)):
        raise Guard("SOURCE_METADATA_CHANGED")
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        a=os.fstat(fd)
        if (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)!=(
            a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns):
            raise Guard("SOURCE_OPEN_RACE")
        raw=os.read(fd,maximum+1)
        b=os.fstat(fd)
        if (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)!=(
            b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns,b.st_ctime_ns):
            raise Guard("SOURCE_READ_RACE")
    finally:os.close(fd)
    if len(raw)!=s.st_size or (sha and hashlib.sha256(raw).hexdigest()!=sha):
        raise Guard("SOURCE_SHA_MISMATCH")
    return raw

def read_unit(target,keys):
    cmd=["/usr/bin/systemctl","show","--no-pager",
         "--property="+",".join(keys),target]
    r=run(cmd)
    if r.returncode:raise Guard("SYSTEMD_PROPERTIES_UNAVAILABLE")
    values={}
    for line in r.stdout.decode("utf8","replace").splitlines():
        name,sep,value=line.partition("=")
        if not sep or name not in keys or name in values or len(value)>8192:
            raise Guard("SYSTEMD_PROPERTIES_INVALID")
        values[name]=value
    if set(values)!=set(keys) or values["Id"]!=target:
        raise Guard("SYSTEMD_UNIT_IDENTITY_MISMATCH")
    return values

def validate_systemd():
    service=read_unit(UNIT,PROPS)
    timer=read_unit(TIMER,TIMER_PROPS)
    identity="argv[]=/usr/bin/python3 -I -B "+str(V2)+" --scheduled-run"
    command=service["ExecStart"]
    if (service["LoadState"]!="loaded" or service["Type"]!="oneshot" or
        service["User"] not in ("","root") or service["ActiveState"]!="failed" or
        service["Result"]!="exit-code" or service["ExecMainStatus"]!="3" or
        service["DropInPaths"]!=str(DROPIN) or
        command.count(identity)!=1 or
        len(re.findall(r"\bpath=([^ ;]+)",command))!=1 or
        "path=/usr/bin/python3" not in command or
        not re.fullmatch(r"[0-9a-fA-F]{32}",service["InvocationID"]) or
        service["InvocationID"]=="0"*32):
        raise Guard("INSTALLED_V2_UNIT_DRIFT")
    if (timer["LoadState"]!="loaded" or timer["ActiveState"]!="active" or
        timer["Unit"]!=UNIT or timer["UnitFileState"]!="enabled"):
        raise Guard("SCHEDULED_TIMER_DRIFT")
    if safe_read(DROPIN,require_root=True,mode=0o644,maximum=2048)!=OLD_DROPIN:
        raise Guard("EXACT_V2_DROPIN_DRIFT")
    for directory in ("/usr","/usr/local","/usr/local/libexec",
                      "/etc","/etc/systemd","/etc/systemd/system",str(DROPIN.parent)):
        s=os.lstat(directory)
        if not stat.S_ISDIR(s.st_mode) or s.st_uid!=0 or s.st_mode&0o022:
            raise Guard("ROOT_PROTECTED_PARENT_DRIFT")
    safe_read(V2,PINNED_V2,require_root=True,mode=0o600,minimum=1024)
    safe_read(V2PARENT,PINNED_V2_PARENT,require_root=True,mode=0o600,minimum=1024)
    if V3.exists() or V3.is_symlink() or V3PARENT.exists() or V3PARENT.is_symlink():
        raise Guard("V3_SOURCE_ALREADY_PRESENT")
    return service

def public_hostkey():
    try:
        entries=socket.getaddrinfo(HOST,22,family=socket.AF_INET,
                                   type=socket.SOCK_STREAM)
        unique={row[4][0] for row in entries if row[0]==socket.AF_INET}
    except OSError:
        raise Guard("DNS_RESOLUTION_FAILED") from None
    if unique!={EXPECTED_IP}:raise Guard("DNS_NOT_VERIFIED_NEW_GCE_IP")
    r=run(["/usr/bin/ssh-keyscan","-T","12","-t","ed25519",
           "-p","22",HOST],25)
    if r.returncode:raise Guard("PUBLIC_HOSTKEY_SCAN_FAILED")
    try:
        lines=[x.strip() for x in r.stdout.decode("ascii","strict").splitlines()
               if x.strip() and not x.lstrip().startswith("#")]
        if len(lines)!=1:raise Guard("PUBLIC_HOSTKEY_SHAPE")
        fields=lines[0].split()
        if len(fields)!=3 or fields[0]!=HOST or fields[1]!="ssh-ed25519":
            raise Guard("PUBLIC_HOSTKEY_SHAPE")
        raw=base64.b64decode(fields[2],validate=True)
        fingerprint="SHA256:"+base64.b64encode(hashlib.sha256(raw).digest()).decode("ascii").rstrip("=")
        if fingerprint!=HOSTKEY_PIN:raise Guard("PUBLIC_HOSTKEY_PIN_MISMATCH")
    except (UnicodeError,ValueError,IndexError):
        raise Guard("PUBLIC_HOSTKEY_SHAPE") from None

def sealed_source_bundle(scratch):
    blobs={}
    for name,pin in SOURCES:
        blobs[name]=safe_read(SRCROOT/name,pin,minimum=100,maximum=131072)
        dest=scratch/name
        fd=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
        try:
            with os.fdopen(fd,"wb") as f:
                f.write(blobs[name]);f.flush();os.fsync(f.fileno())
        except Exception:
            raise Guard("SOURCE_STAGE_WRITE_FAILED") from None
        safe_read(dest,pin,require_root=True,mode=0o600)
    return blobs

def safe_v3_inspect_marker(stdout):
    """Single bounded, exact V3 RESULT token; never expose arbitrary output."""
    if len(stdout)>MAX_OUTPUT:
        return "OUTPUT_OVERSIZE"
    matches=re.findall(rb"(?m)^RESULT=(BLOCKED_[A-Z0-9_]{3,60})$",stdout)
    if len(matches)!=1:return "UNKNOWN"
    return matches[0].decode("ascii")

def v3_safe_direct_category(scratch):
    """When V3 masks parent Block as SAFE, classify only read-only inspect.

    Original audited V3+parent sources are rechecked by SHA; no send, lock,
    authentication, backup, service or Cloudflare mutation. No raw exception
    messages are emitted; only allowlisted codes and exception types.
    """
    import contextlib
    import importlib.util
    import io
    script=scratch/SOURCES[0][0]
    safe_read(script,SOURCES[0][1],require_root=True,mode=0o600,minimum=1024)
    safe_read(scratch/SOURCES[1][0],SOURCES[1][1],require_root=True,mode=0o600,minimum=1024)
    spec=importlib.util.spec_from_file_location("kmj_pinned_v3_readonly_classify",script)
    if spec is None or spec.loader is None:return "IMPORT_UNAVAILABLE"
    module=importlib.util.module_from_spec(spec)
    transport=None
    stage="MODULE_LOAD"
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            spec.loader.exec_module(module)
            stage="TRANSPORT_LOAD"
            transport=module.pinned_transport()
            stage="INSPECT"
            module.inspect(transport,scheduled=False)
    except Exception as exc:
        if isinstance(exc,getattr(module,"Deny",())):
            prefix="DENY_"
        elif transport is not None and isinstance(exc,transport.Block):
            prefix="TRANSPORT_"
        else:
            # This is a *closed* allowlist of exception classes. Classify
            # subclassed OS errors with isinstance, never print exception
            # messages, traceback, exception repr, file or code locations.
            classes=(
              (ModuleNotFoundError,"MODULE_NOT_FOUND"),
              (ImportError,"IMPORT"),
              (NameError,"NAME"),
              (KeyError,"KEY"),
              (IndexError,"INDEX"),
              (FileNotFoundError,"FILE_MISSING"),
              (PermissionError,"PERMISSION"),
              (IsADirectoryError,"IS_DIRECTORY"),
              (NotADirectoryError,"NOT_DIRECTORY"),
              (subprocess.TimeoutExpired,"TIMEOUT"),
              (ConnectionError,"CONNECTION"),
              (TimeoutError,"TIMEOUT"),
              (AttributeError,"ATTRIBUTE"),
              (TypeError,"TYPE"),
              (ValueError,"VALUE"),
              (OSError,"OS_ERROR"),
              (RuntimeError,"RUNTIME"),
              (AssertionError,"ASSERTION"),
              (SyntaxError,"SYNTAX"),
              (OverflowError,"OVERFLOW"),
              (UnicodeError,"UNICODE"),
              (Exception,"OTHER"),
            )
            kind=next(name for klass,name in classes if isinstance(exc,klass))
            return "EXCEPTION_"+stage+"_"+kind
        code=str(exc)
        if re.fullmatch(r"[A-Z][A-Z0-9_]{2,59}",code):
            return prefix+stage+"_"+code
        return prefix+stage+"_UNCLASSIFIED"
    return "DIRECT_READONLY_PASS"

def offline_and_inspect(scratch):
    r=run(["/usr/bin/python3","-I","-B","-m","unittest","discover",
            "-s",str(scratch),"-p",SOURCES[2][0]],90)
    if r.returncode:raise Guard("V3_OFFLINE_REGRESSION_FAILED")
    r=run(["/usr/bin/python3","-I","-B",str(scratch/SOURCES[0][0]),"--selftest"],30)
    if r.returncode or b"RESULT=SELFTEST_PASS" not in r.stdout:
        raise Guard("V3_SELFTEST_FAILED")
    r=run(["/usr/bin/python3","-I","-B",str(scratch/SOURCES[0][0]),"--inspect"],45)
    if (r.returncode or b"RESULT=INSPECT_PASS" not in r.stdout or
        b"GOOGLE_ENDPOINT=DNS_ONLY_STRICT_PINNED_HOSTKEY" not in r.stdout):
        marker=safe_v3_inspect_marker(r.stdout)
        if marker=="BLOCKED_SAFE":
            marker="MASKED_"+v3_safe_direct_category(scratch)
        # No user-directed command, path, exception text or log is printed.
        category="V3_PREFLIGHT_"+marker
        if len(category)>85:category="V3_PREFLIGHT_DIAGNOSIS_TOO_LONG"
        raise Guard(category)
    return True

def exclusive_install(path,data):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    with os.fdopen(fd,"wb") as f:
        f.write(data);f.flush();os.fsync(f.fileno())
    if safe_read(path,hashlib.sha256(data).hexdigest(),require_root=True,mode=0o600)!=data:
        raise Guard("INSTALLED_V3_SHA_MISMATCH")

def atomic_dropin(data,scratch):
    t=scratch/"unit.new"
    fd=os.open(t,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o644)
    with os.fdopen(fd,"wb") as f:
        f.write(data);f.flush();os.fchmod(f.fileno(),0o644);os.fsync(f.fileno())
    if safe_read(t,require_root=True,mode=0o644,maximum=2048)!=data:
        raise Guard("TEMP_DROPIN_DRIFT")
    os.replace(t,DROPIN)

def exact_post_install():
    s=read_unit(UNIT,PROPS)
    cmd=s["ExecStart"]
    exact="argv[]=/usr/bin/python3 -I -B "+str(V3)+" --scheduled-run"
    if (s["DropInPaths"]!=str(DROPIN) or cmd.count(exact)!=1 or
        s["Type"]!="oneshot" or s["User"] not in ("","root") or
        safe_read(DROPIN,require_root=True,mode=0o644,maximum=2048)!=NEW_DROPIN):
        raise Guard("POST_INSTALL_V3_UNIT_DRIFT")
    safe_read(V3,SOURCES[0][1],require_root=True,mode=0o600,minimum=1024)
    safe_read(V3PARENT,SOURCES[1][1],require_root=True,mode=0o600,minimum=1024)
    if read_unit(TIMER,TIMER_PROPS)["ActiveState"]!="active":
        raise Guard("TIMER_NOT_WAITING")
    return s

def classified_receipt(invocation):
    if not re.fullmatch(r"[a-fA-F0-9]{32}",invocation) or invocation=="0"*32:
        raise Guard("BACKUP_INVOCATION_UNVERIFIED")
    r=run(["/usr/bin/journalctl","--no-pager","-o","cat",
           "-n","250","_SYSTEMD_INVOCATION_ID="+invocation],30)
    if r.returncode:raise Guard("BACKUP_JOURNAL_UNAVAILABLE")
    lines=set(r.stdout.decode("utf8","replace").splitlines())
    needed={"FRESH_PGDMP=PASS","SOURCE_MANIFEST=PASS",
            "REMOTE_SFTP_SHA_READBACK=PASS",
            "RESULT=FRESH_PGDUMP_X25519_GOOGLE_TRANSFER_PASS"}
    if not needed.issubset(lines):raise Guard("REMOTE_READBACK_MARKERS_INCOMPLETE")
    return True

def guarded_apply(blobs,previous,scratch):
    # After all dry-run checks, revalidate exact preexisting state and public
    # identity before ANY service mutation or release of private source.
    fresh=validate_systemd()
    if fresh["InvocationID"]!=previous["InvocationID"]:
        raise Guard("SERVICE_CHANGED_SINCE_INSPECT")
    public_hostkey()
    # Keep a persistent root-only original drop-in backup for emergency owner
    # rollback even if this Python process crashes.
    preserve=Path(tempfile.mkdtemp(prefix="kmj-v2-v3-rollback-",dir="/root"))
    preserve.chmod(0o700)
    fd=os.open(preserve/"previous.conf",os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    with os.fdopen(fd,"wb") as f:
        f.write(OLD_DROPIN);f.flush();os.fsync(f.fileno())
    state="SOURCES_PENDING"
    try:
        exclusive_install(V3,blobs[SOURCES[0][0]])
        exclusive_install(V3PARENT,blobs[SOURCES[1][0]])
        atomic_dropin(NEW_DROPIN,scratch)
        state="DROPIN_REPLACED"
        chk=run(["/usr/bin/systemd-analyze","verify",UNIT],45)
        if chk.returncode:raise Guard("SYSTEMD_VERIFY_FAILED")
        if run(["/usr/bin/systemctl","daemon-reload"],45).returncode:
            raise Guard("DAEMON_RELOAD_FAILED")
        exact_post_install()
        # V3 installed-check asserts fixed V3 path, drop-in, source and DNS,
        # but does not send any data or open private SSH auth connections.
        chk=run(["/usr/bin/python3","-I","-B",str(V3),"--installed-check"],45)
        if chk.returncode or b"RESULT=INSPECT_PASS" not in chk.stdout:
            raise Guard("V3_INSTALLED_CHECK_FAILED")
        public_hostkey()
        if run(["/usr/bin/systemctl","reset-failed",UNIT],20).returncode:
            raise Guard("RESET_FAILED_FAILED")
        state="START_REQUESTED"
        start=run(["/usr/bin/systemctl","start",UNIT],1850)
        if start.returncode:raise Guard("REAL_BACKUP_START_FAILED")
        status=read_unit(UNIT,PROPS)
        if (status["Result"]!="success" or status["ExecMainStatus"]!="0" or
            status["ActiveState"]!="inactive" or
            status["InvocationID"]==previous["InvocationID"]):
            raise Guard("BACKUP_SERVICE_RECEIPT_INVALID")
        classified_receipt(status["InvocationID"])
        exact_post_install()
        if safe_read(V3,SOURCES[0][1],require_root=True,mode=0o600)!=blobs[SOURCES[0][0]]:
            raise Guard("SOURCE_CHANGED_AFTER_BACKUP")
        state="COMPLETED"
        print("KMJ_V3_MIGRATION=PASS")
        print("OFFSITE_SERVICE_RESULT=SUCCESS")
        print("REMOTE_SFTP_SHA_READBACK=PASS")
        print("REMOTE_DISPOSABLE_RESTORE=NOT_VERIFIED")
        print("P520_INDEPENDENT_RESTORE=NOT_VERIFIED")
        print("PRODUCTION_RELEASE_MUTATION=NONE")
    except Guard as exc:
        print("KMJ_V3_MIGRATION=BLOCKED_"+str(exc))
        print("BACKUP_SERVICE=NOT_VERIFIED")
        # Never roll back a possibly running service; preserve both executable
        # and old drop-in metadata so the owner can inspect its final state.
        now=read_unit(UNIT,PROPS)
        if state in ("DROPIN_REPLACED","START_REQUESTED") and now["ActiveState"] in ("inactive","failed"):
            if safe_read(DROPIN,require_root=True,mode=0o644,maximum=2048)==NEW_DROPIN:
                atomic_dropin(OLD_DROPIN,scratch)
                if run(["/usr/bin/systemctl","daemon-reload"],45).returncode:
                    print("ROLLBACK=OWNER_REVIEW_REQUIRED")
                else:
                    print("ROLLBACK=PREVIOUS_V2_DROPIN_RESTORED")
            else:
                print("ROLLBACK=OWNER_REVIEW_REQUIRED")
        else:
            print("ROLLBACK=NO_UNSAFE_ACTION")
        raise
    # Root-owned preservation directory intentionally kept, no old source,
    # cipher, archive or customer data removed.

def main(argv):
    if argv not in (["--inspect"],["--apply"]):
        print("KMJ_V3_MIGRATION=BLOCKED_EXACT_MODE_ONLY");return 2
    if os.geteuid()!=0 or socket.gethostname().split(".")[0]!="KMJ-elite":
        print("KMJ_V3_MIGRATION=BLOCKED_ROOT_ELITE_ONLY");return 2
    os.umask(0o077)
    try:
        previous=validate_systemd()
        public_hostkey()
        with tempfile.TemporaryDirectory(prefix="kmj-v3-qa-",dir="/root") as name:
            root=Path(name)
            blobs=sealed_source_bundle(root)
            offline_and_inspect(root)
            print("ORIGINAL_HOSTKEY_PIN=PASS")
            print("DNS_TARGET_VERIFIED=PASS")
            print("INSTALLED_V2_SOURCE=PASS")
            print("V3_OFFLINE_AND_INSPECT=PASS")
            if argv==["--inspect"]:
                print("KMJ_V3_MIGRATION=READ_ONLY_READY")
                print("BACKUP_OR_SYSTEMD_MUTATION=NONE")
                return 0
            guarded_apply(blobs,previous,root)
            return 0
    except (Guard,OSError,subprocess.TimeoutExpired) as exc:
        category=str(exc) if isinstance(exc,Guard) else "FIXED_RUNTIME_UNAVAILABLE"
        if not re.fullmatch(r"[A-Z0-9_]{4,85}",category):category="UNKNOWN"
        print("KMJ_V3_MIGRATION=BLOCKED_"+category)
        print("PRODUCTION_RELEASE_MUTATION=NONE")
        return 3

if __name__=="__main__":
    raise SystemExit(main(sys.argv[1:]))
