#!/usr/bin/env python3
"""KMJ Elite exit-3 offsite service read-only exact-invocation diagnostic.

This cannot run or fix a backup and cannot attest offsite/restore. Root-only
on production for access to the exact journal; outputs ONLY enumerated tokens.
"""
from __future__ import annotations
import os
import re
import subprocess
import sys

UNIT="kmj-elite-offsite-backup.service"
SAFE_ENV={"PATH":"/usr/sbin:/usr/bin:/sbin:/bin","LANG":"C","LC_ALL":"C","HOME":"/root"}
MAX_BYTES=131072
MAX_LINES=200
INVOCATION=re.compile(r"[0-9a-fA-F]{32}\Z")

RULES=(
 ("LOCAL_BACKUP_OR_SOURCE_MISSING",r"missing[_ -]?(dump|backup|source|artifact)|no such file or directory|source[_ -]?not[_ -]?found"),
 ("PINNED_SOURCE_OR_IDENTITY_MISMATCH",r"sha(256)?[_ -]?(mismatch|changed)|hash[_ -]?(mismatch|changed)|pinned[_ -]?(source|sha).*?(mismatch|changed)|owner[_ -]?pin.*?(missing|mismatch)|wrong[_ -]?host"),
 ("LOCAL_CAPACITY_OR_QUOTA",r"no space left on device|disk quota exceeded|space reserve|enospc|edquot"),
 ("REMOTE_NETWORK_OR_DNS",r"network is unreachable|no route to host|temporary failure in name resolution|could not resolve hostname|connection (timed out|refused|reset)|name or service not known"),
 ("REMOTE_HOSTKEY_OR_SSH_AUTH",r"host key verification failed|remote host identification has changed|permission denied \(publickey|too many authentication failures|no mutual signature"),
 ("REMOTE_CIPHER_OR_READBACK_MISMATCH",r"remote[_ -]?(sha|checksum|readback).*?(fail|mismatch)|cipher[_ -]?(sha|checksum).*?(fail|mismatch)|hash[_ -]?readback.*?(fail|mismatch)"),
 ("RECIPIENT_OR_ENCRYPTION_INVALID",r"recipient[_ -]?(invalid|missing|unavailable)|invalid recipient|age[_ -]?(encrypt|recipient).*?(fail|missing)|failed to encrypt"),
 ("LOCAL_FILE_PERMISSIONS",r"permission denied|operation not permitted|unsafe[_ -]?(mode|owner|permissions)|world[_ -]?writable"),
 ("MISSING_TOOL_OR_RUNTIME",r"command not found|executable not found|missing tool|module not found|bad interpreter"),
)
# Reversed by intent: evidence is narrow and never claims a specific issue
# unless one of the literal bounded signatures appears in THIS invocation.
def classify(log: str) -> str:
    if not log:
        return "UNKNOWN_NO_JOURNAL"
    lowered=log[:MAX_BYTES].lower()
    for name,pattern in RULES:
        if re.search(pattern,lowered,re.IGNORECASE):
            return name
    return "UNKNOWN_EXIT3_NEEDS_OWNER_REVIEW"


def parse_properties(raw: str) -> dict:
    fields=("Id","LoadState","ActiveState","SubState","Result",
            "ExecMainStatus","InvocationID")
    out={}
    for line in raw.splitlines():
        key,sep,value=line.partition("=")
        if not sep or key not in fields or key in out or len(value)>128:
            raise ValueError("PROPERTIES_INVALID")
        out[key]=value
    if set(out)!=set(fields) or out["Id"]!=UNIT:
        raise ValueError("UNIT_IDENTITY_UNVERIFIED")
    if not re.fullmatch(r"\d{1,3}",out["ExecMainStatus"]):
        raise ValueError("EXIT_STATUS_UNKNOWN")
    if out["Result"]!="exit-code" or out["ExecMainStatus"]!="3":
        raise ValueError("NOT_CURRENT_EXIT3")
    if not INVOCATION.fullmatch(out["InvocationID"]) or out["InvocationID"]=="0"*32:
        raise ValueError("NO_EXACT_INVOCATION_ID")
    if out["LoadState"]!="loaded" or out["ActiveState"]!="failed":
        raise ValueError("SERVICE_STATE_CHANGED")
    return out


def exact_classify(systemctl_raw: str,journal_raw: str) -> str:
    parse_properties(systemctl_raw)
    return classify(journal_raw)


def main(args: list[str]) -> int:
    if args!=["--inspect"]:
        print("KMJ_OFFSITE_EXIT3=BLOCKED_EXACT_INSPECT_ONLY")
        return 2
    if os.geteuid()!=0 or os.uname().nodename.split(".")[0]!="KMJ-elite":
        print("KMJ_OFFSITE_EXIT3=BLOCKED_ROOT_ELITE_REQUIRED")
        return 2
    def run(cmd: list[str],timeout: int=10) -> str:
        response=subprocess.run(cmd,env=SAFE_ENV,cwd="/",stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                                check=False,timeout=timeout)
        if response.returncode!=0 or len(response.stdout)>MAX_BYTES:
            raise ValueError("COMMAND_FAILED_OR_OVERSIZED")
        return response.stdout.decode("utf8",errors="replace")
    try:
        unit_cmd=["/usr/bin/systemctl","show","--no-pager",
                  "--property=Id,LoadState,ActiveState,SubState,Result,ExecMainStatus,InvocationID",UNIT]
        props=run(unit_cmd)
        fields=parse_properties(props)
        log=run(["/usr/bin/journalctl","--no-pager","-o","cat",
                 "-n",str(MAX_LINES),
                 "_SYSTEMD_INVOCATION_ID="+fields["InvocationID"]],15)
        # A concurrent timer/service restart must not attach stale invocation
        # journal messages to the current failed unit. Re-read fixed metadata
        # and accept only if the complete identity and state match exactly.
        after=parse_properties(run(unit_cmd))
        if after!=fields:
            raise ValueError("INVOCATION_CHANGED")
        # A successful journal query with zero matching rows does NOT attest
        # a cause or a valid backup.
        result=classify(log)
    except (ValueError,OSError,subprocess.TimeoutExpired):
        print("KMJ_OFFSITE_EXIT3=BLOCKED_EXACT_INVOCATION_UNVERIFIED")
        print("BACKUP_REPAIR=NOT_ATTEMPTED")
        return 2
    print("KMJ_OFFSITE_EXIT3=READ_ONLY_CLASSIFIED")
    print("SYSTEMD_EXIT=3")
    print("JOURNAL_SCOPE=EXACT_INVOCATION")
    print("FAILURE_CLASS="+result)
    print("RAW_JOURNAL_EXPOSED=NO")
    print("BACKUP_REPAIR=NOT_ATTEMPTED")
    print("OFFHOST_BACKUP_VERIFIED=NO")
    print("PRODUCTION_APPROVAL=UNCHANGED")
    return 0

if __name__=="__main__":
    sys.exit(main(sys.argv[1:]))
