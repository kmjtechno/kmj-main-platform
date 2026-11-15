#!/usr/bin/env python3
"""KMJ root-only operator receipt adapter (v1).

Owner runs this adapter only for one fixed, hash-pinned read-only command.
It executes an immutable private copy and writes a sanitized receipt inside
the authorized CodeBridge project. It never accepts shell/argv/path inputs.
The CodeBridge read_file tool can inspect the stable receipt across chats.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import tempfile

PROJECT=Path("/srv/kmj-codebridge-projects/kmj-main-platform")
QA=PROJECT/"work/qa"
RECEIPTS=QA/"operator-receipts"
CURRENT="/home/kmjprod/releases/platform-8070dad72c55"
PINNED_SOURCE=QA/"KMJ_P0_LEGACY_CODEBRIDGE_PRIVATE_PORT_18787_GUARDED_FIX_20261027.py"
PINNED_SHA256="79c21f19c6f86da7af97927491c81644e18fefc9c36d291475f33fd48bfe9279"
TASK="gateway-port-verify"

PATTERNS={
 "EXACT_TARGET_RELEASE":r"^platform-8070dad72c55$",
 "GATEWAY_SYSTEMD":r"^ACTIVE$",
 "GATEWAY_PID_PRESENT":r"^YES$",
 "GATEWAY_BIND":r"^LOOPBACK_ONLY$",
 "ACTUAL_GATEWAY_PORT":r"^18787$",
 "APP_CONFIGURED_PORT":r"^\d{2,5}$",
 "PORT_ALIGNMENT":r"^(PASS|MISMATCH)$",
 "LIVE_PUBLIC_AGENT_ORIGIN_SUPPORT":r"^NO_LEGACY_RELEASE$",
 "SYSTEM_CHANGES":r"^NONE$",
 "KMJ_PRIVATE_GATEWAY_ALIGNMENT":r"^(INSPECT_ONLY|BLOCKED_[A-Z0-9_]{1,80})$",
}

def fail(cause):
    print("KMJ_OPERATOR_RECEIPT=BLOCKED_"+cause,flush=True)
    raise SystemExit(2)

def secure_file_bytes(path):
    if not path.is_file() or path.is_symlink():
        fail("SOURCE_MISSING_OR_SYMLINK")
    raw=path.read_bytes()
    if len(raw)>65536 or hashlib.sha256(raw).hexdigest()!=PINNED_SHA256:
        fail("PINNED_SOURCE_HASH")
    return raw

def guarded_directory():
    if not PROJECT.is_dir() or PROJECT.is_symlink():
        fail("PROJECT_DIRECTORY")
    if not QA.is_dir() or QA.is_symlink():
        fail("QA_DIRECTORY")
    if RECEIPTS.is_symlink():
        fail("RECEIPTS_SYMLINK")
    RECEIPTS.mkdir(mode=0o755,exist_ok=True)
    st=RECEIPTS.stat()
    if not stat.S_ISDIR(st.st_mode) or st.st_mode & 0o022:
        fail("RECEIPTS_DIRECTORY_INSECURE")
    # Current authorized read-only CodeBridge agents must be able to traverse.
    if st.st_mode & 0o005 != 0o005:
        fail("RECEIPTS_DIRECTORY_NOT_TRAVERSABLE")

def atomic_receipt(name,data):
    fd,path=tempfile.mkstemp(prefix=".kmj-receipt-",dir=RECEIPTS)
    temp=Path(path)
    try:
        with os.fdopen(fd,"wb") as out:
            os.fchmod(out.fileno(),0o644)
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        dest=RECEIPTS/name
        if dest.is_symlink():
            fail("RECEIPT_TARGET_SYMLINK")
        os.replace(temp,dest)
        dirfd=os.open(RECEIPTS,os.O_RDONLY|os.O_DIRECTORY)
        try: os.fsync(dirfd)
        finally: os.close(dirfd)
    finally:
        if temp.exists(): temp.unlink()

def run_exact(raw):
    fd,path=tempfile.mkstemp(prefix=".kmj-operator-pinned-",suffix=".py",dir="/root")
    temp=Path(path)
    try:
        with os.fdopen(fd,"wb") as out:
            os.fchmod(out.fileno(),0o400)
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        result=subprocess.run(
            [sys.executable,"-B",str(temp)],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            timeout=25,check=False,env={"PATH":"/usr/sbin:/usr/bin:/sbin:/bin",
                                         "LANG":"C.UTF-8","HOME":"/root"},
            cwd="/",text=True,
        )
        # Do not return, write, or echo raw process output.
        out=result.stdout if len(result.stdout.encode("utf-8"))<=16384 else ""
        invalid_size=out==""
        return result.returncode,out,invalid_size,False
    except subprocess.TimeoutExpired:
        return 124,"",True,True
    finally:
        if temp.exists(): temp.unlink()

def main():
    parser=argparse.ArgumentParser(description="Run one approved root-only read-only profile and publish sanitized CodeBridge result")
    parser.add_argument("--task",choices=[TASK],required=True)
    args=parser.parse_args()
    if os.geteuid()!=0 or socket.gethostname().split(".")[0]!="KMJ-elite":
        fail("ROOT_ON_ELITE_REQUIRED")
    if not Path("/home/kmjprod/current").is_symlink() or str(Path("/home/kmjprod/current").resolve())!=CURRENT:
        fail("PRODUCTION_RELEASE_DRIFT")
    guarded_directory()
    raw=secure_file_bytes(PINNED_SOURCE)
    exit_code,output,oversize,timed_out=run_exact(raw)
    checks={}
    duplicate=False
    for line in output.splitlines():
        if len(line)>160 or "=" not in line: continue
        key,value=line.split("=",1)
        pattern=PATTERNS.get(key)
        if pattern is None: continue
        if key in checks: duplicate=True
        if re.fullmatch(pattern,value,flags=re.ASCII):
            checks[key]=value
    passed=(exit_code==0 and not duplicate and not oversize and not timed_out
            and checks.get("GATEWAY_SYSTEMD")=="ACTIVE"
            and checks.get("ACTUAL_GATEWAY_PORT")=="18787"
            and checks.get("APP_CONFIGURED_PORT")=="18787"
            and checks.get("PORT_ALIGNMENT")=="PASS"
            and checks.get("SYSTEM_CHANGES")=="NONE"
            and checks.get("KMJ_PRIVATE_GATEWAY_ALIGNMENT")=="INSPECT_ONLY")
    document={
      "schema":"kmj.codebridge.operator-receipt.v1",
      "task":args.task,"source":"owner_root_sha_pinned_profile",
      "timestamp_utc":datetime.now(timezone.utc).isoformat(timespec="seconds"),
      "pinned_script_sha256":PINNED_SHA256,
      "app_release":Path(CURRENT).name,
      "exit_code":exit_code,
      "verdict":"PASS" if passed else "BLOCKED",
      "operator_execution":True,
      "codebridge_automated_approval":False,
      "receipt_is_not_release_approval":True,
      "checks":checks,
      "truncated_or_timeout":bool(oversize or timed_out),
    }
    payload=(json.dumps(document,sort_keys=True,separators=(",",":"),ensure_ascii=True)+"\n").encode("ascii")
    if len(payload)>4096: fail("RECEIPT_TOO_LARGE")
    atomic_receipt(args.task+".json",payload)
    atomic_receipt("latest.json",payload)
    print("KMJ_OPERATOR_RECEIPT_SAVED=PASS")
    print("CODEBRIDGE_READ_PATH=work/qa/operator-receipts/"+args.task+".json")
    print("CODEBRIDGE_LATEST_PATH=work/qa/operator-receipts/latest.json")
    print("RECEIPT_SHA256="+hashlib.sha256(payload).hexdigest())
    print("GATEWAY_PORT_QA="+document["verdict"])
    print("PRODUCTION_ACTIVATION=NOT_ATTEMPTED")
    if not passed:
        raise SystemExit(2)

if __name__=="__main__":
    main()
