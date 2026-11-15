#!/usr/bin/python3
"""SOURCE REVIEW ONLY: root-pinned V2 provenance for future V3 backup runner.

No executable CLI, backup, SFTP connection, root grant, systemd change or
restoration. A future owner-approved signed V3 entrypoint may use this exact
fixed admission before the source-only transfer-bound transaction module.

Verify fixed installed V2 module SHA, fixed SFTP transport SHA, every parent
directory's ownership and no-symlink, and the exact active systemd unit
contract. Import the exact pinned V2 source only after all checks. Do not
allow caller-selectable commands, paths, units, SHAs or privilege grants.
Admission verifies CODE/UNIT identity, NOT a completed backup or restore.
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
import types

ROOT=Path("/usr/local/libexec")
V2=ROOT/"kmj-offsite-fresh-x25519-v2-20261112.py"
V2_SHA="fb6ec4a4c5f0189562d35141765dcfcea84bc1cec3d8f4b79362e33d884b281e"
TRANSPORT=ROOT/"KMJ_OFFSITE_SFTP_31LINE_GUARDED_REPAIR_20261111.py"
TRANSPORT_SHA="3535f47c7cb49924d929978993553359f3f16320c34d11bd251de3fe1936d37f"
UNIT="kmj-elite-offsite-backup.service"
DROPIN="/etc/systemd/system/kmj-elite-offsite-backup.service.d/97-kmj-offsite-fresh-x25519-20261112.conf"
FIELDS=("Id","LoadState","Type","User","ExecStart","DropInPaths")
ENV={"PATH":"/usr/sbin:/usr/bin:/sbin:/bin","LC_ALL":"C","LANG":"C","HOME":"/root"}


class Deny(Exception):
    pass


def root_parent_chain():
    for name in ("/usr","/usr/local","/usr/local/libexec"):
        st=os.lstat(name)
        if not (stat.S_ISDIR(st.st_mode) and st.st_uid==0
                and st.st_mode&0o022==0):
            raise Deny("ROOT_PARENT_CHAIN_UNTRUSTED")


def pinned_source_bytes(path,sha,*,uid=0,minimum=256,maximum=131072):
    if (not isinstance(path,Path) or not isinstance(sha,str)
            or re.fullmatch(r"[a-f0-9]{64}",sha) is None):
        raise Deny("PINNED_FILE_INPUT_INVALID")
    before=os.lstat(path)
    if (not stat.S_ISREG(before.st_mode) or before.st_uid!=uid
            or before.st_nlink!=1 or stat.S_IMODE(before.st_mode)!=0o600
            or not minimum<=before.st_size<=maximum):
        raise Deny("PINNED_FILE_METADATA_CHANGED")
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        after=os.fstat(fd)
        if ((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,
             before.st_ctime_ns,before.st_nlink)!=
            (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,
             after.st_ctime_ns,after.st_nlink)):
            raise Deny("PINNED_FILE_RACE")
        raw=os.read(fd,maximum+1)
    finally:
        os.close(fd)
    if len(raw)!=before.st_size or hashlib.sha256(raw).hexdigest()!=sha:
        raise Deny("PINNED_FILE_SHA_CHANGED")
    return raw


def validate_unit(props):
    if (set(props)!=set(FIELDS)
            or props.get("Id")!=UNIT
            or props.get("LoadState")!="loaded"
            or props.get("Type")!="oneshot"
            or props.get("User") not in ("","root")
            or props.get("DropInPaths")!=DROPIN):
        raise Deny("SCHEDULED_V2_UNIT_ADMISSION_FAILED")
    start=props["ExecStart"]
    marker="argv[]=/usr/bin/python3 -I -B "+str(V2)+" --scheduled-run"
    if (start.count(marker)!=1
            or len(start)>4096
            or not re.search(r"(?:^|[ ;])path=/usr/bin/python3(?:[ ;]|$)",start)):
        raise Deny("SCHEDULED_V2_EXEC_IDENTITY_CHANGED")
    return True


def fixed_unit_info():
    args=["/usr/bin/systemctl","show","--no-pager"]
    for key in FIELDS:
        args.extend(("-p",key))
    args.append(UNIT)
    try:
        run=subprocess.run(args,cwd="/",env=ENV,stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                           timeout=12,check=False)
    except (OSError,subprocess.TimeoutExpired):
        raise Deny("SCHEDULED_UNIT_UNAVAILABLE") from None
    if run.returncode!=0 or len(run.stdout)>8192:
        raise Deny("SCHEDULED_UNIT_OUTPUT_NOT_TRUSTED")
    props={}
    for line in run.stdout.decode("ascii",errors="strict").splitlines():
        if "=" not in line:
            raise Deny("SCHEDULED_UNIT_OUTPUT_NOT_TRUSTED")
        k,v=line.split("=",1)
        if k not in FIELDS or k in props or "\x00" in v:
            raise Deny("SCHEDULED_UNIT_OUTPUT_NOT_TRUSTED")
        props[k]=v
    validate_unit(props)
    return props


def admit_exact_installed_v2():
    """Admission only; returns pinned module + V2 transport without SFTP I/O."""
    if os.geteuid()!=0 or socket.gethostname().split(".")[0]!="KMJ-elite":
        raise Deny("OWNER_HOST_ROOT_REQUIRED")
    root_parent_chain()
    # Read both bytes BEFORE any import and before unit verification.
    source=pinned_source_bytes(V2,V2_SHA)
    pinned_source_bytes(TRANSPORT,TRANSPORT_SHA)
    fixed_unit_info()
    m=types.ModuleType("kmj_owner_exact_v2_transport_source")
    m.__file__=str(V2)
    exec(compile(source,str(V2),"exec"),m.__dict__)
    if (m.SCHEDULED!=V2 or m.PARENT_SHA!=TRANSPORT_SHA
            or m.PARENT!=TRANSPORT.name):
        raise Deny("V2_SOURCE_IMPORT_CONTRACT_CHANGED")
    # V2 pinned_transport itself reads the root-owned transport with nofollow
    # and checks its SHA before importing; never invokes transfer() here.
    t=m.pinned_transport()
    pinned_source_bytes(V2,V2_SHA)
    pinned_source_bytes(TRANSPORT,TRANSPORT_SHA)
    if not all(callable(getattr(t,name,None)) for name in
               ("transfer","digest_cipher","host_key")):
        raise Deny("V2_PINNED_TRANSPORT_INTERFACE_CHANGED")
    return m,t


def admission_selftest():
    assert len(V2_SHA)==64 and len(TRANSPORT_SHA)==64
    assert V2.parent==TRANSPORT.parent==ROOT
    assert V2.name.endswith("20261112.py")
    assert DROPIN.endswith("20261112.conf")
    print("KMJ_V3_V2_ADMISSION_SOURCE_ONLY_SELFTEST=PASS")
    print("SOURCE_OR_SERVICE_MUTATION=NONE")
    return 0


if __name__=="__main__":
    print("KMJ_V3_PINNED_V2_ADMISSION=SOURCE_ONLY_NOT_INSTALLED")
    raise SystemExit(2)
