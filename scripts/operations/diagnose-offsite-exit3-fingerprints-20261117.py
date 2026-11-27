#!/usr/bin/env python3
"""Exact-invocation, root-only, no-secret marker fingerprints for offsite exit 3.

Only SHA256 hashes of fixed-format guard identifiers leave this process.
Do not print raw journal, marker values, paths, ExecStart or credentials.
"""
from __future__ import annotations
import hashlib
import os
import re
import subprocess
import sys

UNIT = "kmj-elite-offsite-backup.service"
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C",
       "LC_ALL": "C", "HOME": "/root"}
MAX_BYTES = 131072
MAX_LINES = 200
PROPS = ("Id","LoadState","ActiveState","SubState","Result",
         "ExecMainStatus","InvocationID")
INVOCATION = re.compile(r"[a-fA-F0-9]{32}\Z")
# ASCII-only fixed structured tokens; no untrusted name is ever printed.
KEYED = re.compile(
    r"(?<![A-Za-z0-9_])(?P<key>KMJ_[A-Z0-9_]{2,60}|RESULT|STATUS)"
    r"=(?P<value>BLOCKED(?:_[A-Z0-9_]{1,70})?|FAILED(?:_[A-Z0-9_]{1,70})?|"
    r"FAIL(?:_[A-Z0-9_]{1,70})?|ERROR(?:_[A-Z0-9_]{1,70})?)(?![A-Za-z0-9_])"
)
LOOSE = re.compile(r"(?<![A-Za-z0-9_])BLOCKED_[A-Z0-9_]{2,70}(?![A-Za-z0-9_])")

def parse_systemd(raw):
    values = {}
    for line in raw.splitlines():
        k, sep, v = line.partition("=")
        if not sep or k not in PROPS or k in values or len(v) > 128:
            raise ValueError("INVALID_SYSTEMD_METADATA")
        values[k] = v
    if set(values) != set(PROPS) or values["Id"] != UNIT or \
       values["LoadState"] != "loaded" or values["ActiveState"] != "failed" or \
       values["Result"] != "exit-code" or values["ExecMainStatus"] != "3" or \
       not INVOCATION.fullmatch(values["InvocationID"]) or \
       values["InvocationID"].lower() == "0"*32:
        raise ValueError("NOT_CURRENT_EXACT_EXIT3")
    return values

def scan(log):
    if not isinstance(log, str) or len(log.encode("utf-8")) > MAX_BYTES:
        raise ValueError("OVERSIZED_JOURNAL")
    # Keyed regex already includes its BLOCKED suffix. Suppress overlapping
    # standalone matches so a single diagnostic isn't counted twice.
    matches = []
    for entry in KEYED.finditer(log):
        matches.append((entry.start(), entry.end(), "KEYED",
                        entry.group("key"), entry.group("value")))
    for entry in LOOSE.finditer(log):
        if any(start <= entry.start() and entry.end() <= end
               for start,end,kind,key,value in matches):
            continue
        matches.append((entry.start(),entry.end(),"STANDALONE","NONE",entry.group()))
    matches.sort(key=lambda x:x[0])
    unique = []
    seen = set()
    for _start,_end,kind,key,value in matches:
        token = (kind,key,value)
        if token not in seen:
            seen.add(token)
            unique.append(token)
    return len(matches),unique

def digest(token):
    return hashlib.sha256(token.encode("ascii")).hexdigest()

def capture(command,timeout=12):
    output = subprocess.run(command,env=ENV,cwd="/",stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                            check=False,timeout=timeout)
    if output.returncode != 0 or len(output.stdout) > MAX_BYTES:
        raise ValueError("COMMAND_FAILED_OR_OVERSIZED")
    return output.stdout.decode("utf-8",errors="replace")

def inspect():
    if os.geteuid() != 0 or os.uname().nodename.split(".")[0] != "KMJ-elite":
        raise ValueError("ROOT_ELITE_REQUIRED")
    unit_command = ["/usr/bin/systemctl","show","--no-pager",
        "--property="+",".join(PROPS),UNIT]
    before = parse_systemd(capture(unit_command))
    journal = capture(["/usr/bin/journalctl","--no-pager","-o","cat",
                       "-n",str(MAX_LINES),
                       "_SYSTEMD_INVOCATION_ID="+before["InvocationID"]],15)
    after = parse_systemd(capture(unit_command))
    if after != before:
        raise ValueError("INVOCATION_CHANGED")
    return scan(journal)

def main(args):
    if args != ["--inspect"]:
        print("KMJ_EXIT3_FINGERPRINT=BLOCKED_EXACT_INSPECT_ONLY")
        return 2
    try:
        appearances,unique = inspect()
        if appearances > MAX_LINES*2:
            raise ValueError("TOO_MANY_MARKERS")
    except (ValueError,OSError,subprocess.TimeoutExpired,UnicodeError):
        print("KMJ_EXIT3_FINGERPRINT=BLOCKED_EXACT_INVOCATION_UNVERIFIED")
        print("PRODUCTION_APPROVAL=UNCHANGED")
        return 2
    print("KMJ_EXIT3_FINGERPRINT=READ_ONLY")
    print("JOURNAL_SCOPE=EXACT_INVOCATION")
    print("MARKER_APPEARANCES_BOUND="+str(appearances))
    print("DISTINCT_MARKERS_BOUND="+str(len(unique)))
    print("FINGERPRINTS_EMITTED="+str(min(len(unique),3)))
    for index,(kind,key,value) in enumerate(unique[:3],1):
        print("MARKER_"+str(index)+"_KIND="+kind)
        print("MARKER_"+str(index)+"_KEY_SHA256="+digest(key))
        print("MARKER_"+str(index)+"_REASON_SHA256="+digest(value))
    print("RAW_JOURNAL_EXPOSED=NO")
    print("BACKUP_REPAIR=NOT_ATTEMPTED")
    print("OFFHOST_BACKUP_VERIFIED=NO")
    print("PRODUCTION_APPROVAL=UNCHANGED")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
