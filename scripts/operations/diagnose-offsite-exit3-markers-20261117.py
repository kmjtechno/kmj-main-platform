#!/usr/bin/env python3
"""Second-stage read-only marker triage for KMJ-elite offsite exit 3.

Never prints journal text, command lines, paths, marker values or secrets.
No service restart, backup, transfer, deployment or approval. Owner-only root
inspection of the SAME exact failed invocation used by PR890 classifier.
"""
from __future__ import annotations
import os
import re
import subprocess
import sys

UNIT="kmj-elite-offsite-backup.service"
ENV={"PATH":"/usr/sbin:/usr/bin:/sbin:/bin","LANG":"C","LC_ALL":"C","HOME":"/root"}
MAX_BYTES=131072
MAX_LINES=200
HEX32=re.compile(r"[a-fA-F0-9]{32}\Z")
KEY=re.compile(r"(?:KMJ_[A-Z0-9_]{2,60}|RESULT|STATUS)")
MARKER=re.compile(r"\b(?:KMJ_[A-Z0-9_]{2,60}|RESULT|STATUS)=(?:BLOCKED|FAILED|FAIL|ERROR)(?:_[A-Z0-9_]{1,70})?\b")
BLOCKER_WORD=re.compile(r"\bBLOCKED[_-][A-Z0-9_]{2,70}\b")
SAFE_ENUM=re.compile(r"[A-Z0-9_]{1,80}\Z")
PROPS=("Id","LoadState","ActiveState","SubState","Result","ExecMainStatus","InvocationID")

def snapshot(raw: str) -> dict[str,str]:
    found={}
    for line in raw.splitlines():
        key,sep,value=line.partition("=")
        if not sep or key not in PROPS or key in found or len(value)>128:
            raise ValueError("INVALID_SYSTEMD_METADATA")
        found[key]=value
    if set(found)!=set(PROPS) or found["Id"]!=UNIT or found["LoadState"]!="loaded" or found["ActiveState"]!="failed" or found["Result"]!="exit-code" or found["ExecMainStatus"]!="3":
        raise ValueError("NOT_EXACT_FAILED_UNIT")
    ident=found["InvocationID"]
    if not HEX32.fullmatch(ident) or ident.lower()=="0"*32:
        raise ValueError("INVALID_INVOCATION")
    return found

# Only fixed category identifiers leave process memory; never echo actual tokens.
KEYWORDS=(
    ("SOURCE_PIN_OR_IDENTITY_GUARD",("SHA","PIN","DIGEST","HASH","IDENTITY","WRONG_HOST","MISMATCH","SIGNED")),
    ("DATABASE_OR_DUMP_GUARD",("PGDMP","PG_DUMP","DATABASE","DUMP","POSTGRES","RESTORE")),
    ("STORAGE_OR_UPLOADS_GUARD",("STORAGE","UPLOAD","DIRECTORY","SOURCE_TREE","FILE_TYPE","SYMLINK","LINK","ARCHIVE")),
    ("REMOTE_TRANSFER_OR_READBACK_GUARD",("SFTP","REMOTE","READBACK","SSH","HOSTKEY","NETWORK","TRANSFER","GOOGLE","CIPHER")),
    ("CRYPTO_OR_RECIPIENT_GUARD",("X25519","ENCRYPT","AGE","RECIPIENT","KEY","DECRYPT")),
    ("PERMISSION_OR_OWNERSHIP_GUARD",("PERMISSION","MODE","OWNER","ROOT","ACL","ACCESS","UNSAFE")),
    ("RESOURCE_OR_FRESHNESS_GUARD",("SPACE","QUOTA","FRESH","FRESHNESS","MISSING","TIME","EXPIRED","RETENTION","DATE")),
    ("CONFIG_OR_RUNTIME_GUARD",("ENV","CONFIG","RUNTIME","TOOL","DEPENDENCY","SERVICE","TIMER","EXEC")),
    ("APPROVAL_OR_POLICY_GUARD",("APPROVAL","APPROVED","POLICY","GATE","LOCK","PROTECTED")),
)
HUMAN_HINTS=(
    ("CAPACITY_MESSAGE",re.compile(r"no space left on device|quota exceeded|disk quota exceeded",re.I)),
    ("PERMISSIONS_MESSAGE",re.compile(r"permission denied|operation not permitted",re.I)),
    ("CONNECTION_MESSAGE",re.compile(r"connection refused|connection timed out|no route to host|could not resolve hostname",re.I)),
    ("REMOTE_HOSTKEY_MESSAGE",re.compile(r"host key verification failed|permission denied \(publickey",re.I)),
    ("MISSING_FILE_MESSAGE",re.compile(r"no such file or directory|not found",re.I)),
)
def triage(log: str) -> tuple[str,str,int,int]:
    if not isinstance(log,str) or len(log.encode("utf8"))>MAX_BYTES:
        raise ValueError("OVERSIZED_JOURNAL")
    lines=log.splitlines()
    found=MARKER.findall(log)
    # General BLOCKED_* script guard messages not anchored by key=value.
    found+=BLOCKER_WORD.findall(log)
    if found:
        # Each marker contributes ONLY its categorical keyword, never raw code.
        for category,words in KEYWORDS:
            for token in found:
                if any(re.search(r"(?:^|_)"+re.escape(w)+r"(?:_|$)",token) for w in words):
                    return "GUARD_MARKERS_PRESENT",category,min(len(lines),MAX_LINES),min(len(found),MAX_LINES)
        return "GUARD_MARKERS_PRESENT","OTHER_PROTECTED_GUARD",min(len(lines),MAX_LINES),min(len(found),MAX_LINES)
    for category,pattern in HUMAN_HINTS:
        if pattern.search(log):
            return "NO_GUARD_MARKERS",category,min(len(lines),MAX_LINES),0
    return ("NO_GUARD_MARKERS","NO_CLASSIFIABLE_MARKER" if lines else "EMPTY_JOURNAL",
            min(len(lines),MAX_LINES),0)

def capture(argv: list[str],seconds: int=10) -> str:
    result=subprocess.run(argv,env=ENV,cwd="/",stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                          check=False,timeout=seconds)
    if result.returncode!=0 or len(result.stdout)>MAX_BYTES:
        raise ValueError("INSPECTION_UNAVAILABLE")
    return result.stdout.decode("utf8",errors="replace")

def inspect() -> tuple[str,str,int,int]:
    if os.geteuid()!=0 or os.uname().nodename.split(".")[0]!="KMJ-elite":
        raise ValueError("ROOT_ELITE_REQUIRED")
    cmd=["/usr/bin/systemctl","show","--no-pager",
         "--property="+",".join(PROPS),UNIT]
    before=snapshot(capture(cmd))
    journal=capture(["/usr/bin/journalctl","--no-pager","-o","cat",
                     "-n",str(MAX_LINES),
                     "_SYSTEMD_INVOCATION_ID="+before["InvocationID"]],15)
    after=snapshot(capture(cmd))
    if before!=after:
        raise ValueError("INVOCATION_CHANGED")
    return triage(journal)

def main(argv: list[str]) -> int:
    if argv!=["--inspect"]:
        print("KMJ_EXIT3_MARKERS=BLOCKED_EXACT_INSPECT_ONLY")
        return 2
    try:
        kind,category,nlines,nmarkers=inspect()
        if not all(SAFE_ENUM.fullmatch(t) for t in [kind,category]):
            raise ValueError("UNSAFE_RECEIPT")
    except (ValueError, OSError, subprocess.TimeoutExpired, UnicodeError):
        print("KMJ_EXIT3_MARKERS=BLOCKED_EXACT_INVOCATION_UNVERIFIED")
        print("PRODUCTION_APPROVAL=UNCHANGED")
        return 2
    print("KMJ_EXIT3_MARKERS=READ_ONLY_INSPECTED")
    print("JOURNAL_SCOPE=EXACT_INVOCATION")
    print("MARKER_SCOPE="+kind)
    print("GUARD_REASON_CLASS="+category)
    print("JOURNAL_LINES_BOUND="+str(nlines))
    print("GUARD_MARKERS_BOUND="+str(nmarkers))
    print("RAW_LOG_EXPOSED=NO")
    print("BACKUP_REPAIR=NOT_ATTEMPTED")
    print("PRODUCTION_APPROVAL=UNCHANGED")
    return 0

if __name__=="__main__":
    sys.exit(main(sys.argv[1:]))
