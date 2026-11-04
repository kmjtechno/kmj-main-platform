#!/usr/bin/env python3
"""Read-only exact-candidate staging prerequisites on KMJ-elite.

No secret files read, release switch, approval edit, service control, network,
backup, environment inheritance, or staging mutation. Advisory only.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import re
import socket
import stat
import sys

CAND = "a9796a25a2801cd303a69f5ad468aa9a704e5fff"
OLD_STAGE = "b2e69decab3acd861e94e11992cd8a4cff4f2b94"
PROD = Path("/home/kmjprod/current")
PROD_EXPECTED = "platform-574e443a2c75"
SITE = Path("/home/kmjstage/htdocs/staging.kmjtechno.com")
STAGE_PARENT = Path("/home/kmjstage/releases")
NEW_STAGE = STAGE_PARENT / CAND
SOURCE = Path("/home/kmjprod/releases") / ("platform-" + CAND[:12]) / "apps/platform"
SEAL = Path("/etc/kmj-codebridge") / ("main-platform-staging-seal-" + CAND + ".sha256")
APPROVAL = Path("/etc/kmj-codebridge/main-platform-staging-approval.json")
RUNNER = Path("/usr/local/libexec/kmj-codebridge/kmj-main-platform-staging-deploy.sh")
UNIT = Path("/etc/systemd/system/kmj-main-platform-staging-deploy.service")
EXPECTED_RUNNER = "9713b608e2cd8c8c9f0ad4f56e475f035b86bf889ef0cc164f9aa9532ad2d7ab"
EXPECTED_UNIT = "21e8566433cfbb7c86864844df68295fb1dd420b87ec21aa541a35a1656c9919"


def emit(k, v):
    print(k + "=" + v, flush=True)


def shape(p):
    try:
        i = os.lstat(p)
    except OSError:
        return "ABSENT"
    if stat.S_ISLNK(i.st_mode):
        return "LINK_UNTRUSTED"
    if not stat.S_ISDIR(i.st_mode):
        return "NOT_DIRECTORY"
    return "DIRECTORY_PRESENT_UNATTESTED"


def link(p, acceptable):
    try:
        if not stat.S_ISLNK(os.lstat(p).st_mode):
            return "NOT_LINK"
        return "EXPECTED" if os.readlink(p) in acceptable else "DRIFT"
    except OSError:
        return "ABSENT_OR_UNREADABLE"


def protected_file_digest(path, expected):
    parent = path.parent
    while True:
        try:
            x = os.lstat(parent)
            if not stat.S_ISDIR(x.st_mode) or x.st_uid != 0 or x.st_mode & 0o022:
                return "UNTRUSTED_ANCESTOR"
        except OSError:
            return "UNTRUSTED_ANCESTOR"
        if parent == Path("/"):
            break
        parent = parent.parent
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError:
        return "MISSING_OR_UNTRUSTED"
    try:
        st = os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_nlink != 1
                or st.st_size < 1 or st.st_size > 131072 or st.st_mode & 0o022):
            return "UNTRUSTED_METADATA"
        data = os.read(fd, 131073)
        after = os.fstat(fd)
        if (len(data) != st.st_size or st.st_mtime_ns != after.st_mtime_ns
                or st.st_ctime_ns != after.st_ctime_ns):
            return "UNSTABLE_CONTENT"
        return "MATCH" if hashlib.sha256(data).hexdigest() == expected else "DIGEST_MISMATCH"
    finally:
        os.close(fd)


def basic_root_file(p):
    try:
        s = os.lstat(p)
    except OSError:
        return "MISSING_OR_UNTRUSTED"
    return ("ROOT_REGULAR_PRESENT_UNATTESTED" if stat.S_ISREG(s.st_mode)
            and s.st_uid == 0 and s.st_nlink == 1 and not s.st_mode & 0o022
            else "UNTRUSTED")


def main():
    if (len(sys.argv) != 1 or os.geteuid() != 0
            or socket.gethostname().split(".")[0].lower() != "kmj-elite"):
        emit("STAGING_PREP", "BLOCKED_ROOT_HOST_OR_ARGS")
        return 2
    emit("STAGING_PREP", "READ_ONLY_V1")
    emit("PRODUCTION_POINTER", link(PROD, {
        "/home/kmjprod/releases/" + PROD_EXPECTED, "releases/" + PROD_EXPECTED}))
    emit("CURRENT_STAGE_POINTER", link(SITE, {
        str(STAGE_PARENT / OLD_STAGE / "apps/platform"),
        "../releases/" + OLD_STAGE + "/apps/platform"}))
    emit("PRODUCTION_CANDIDATE", shape(SOURCE))
    emit("STAGE_RELEASES_PARENT", shape(STAGE_PARENT))
    emit("STAGING_EXACT_CANDIDATE", shape(NEW_STAGE))
    emit("STAGING_EXACT_APP", shape(NEW_STAGE / "apps/platform"))
    emit("ROOT_STAGING_SEAL", basic_root_file(SEAL))
    emit("STAGING_PROTECTED_APPROVAL", basic_root_file(APPROVAL))
    emit("STAGING_RUNNER_DIGEST", protected_file_digest(RUNNER, EXPECTED_RUNNER))
    emit("STAGING_UNIT_DIGEST", protected_file_digest(UNIT, EXPECTED_UNIT))
    emit("ROOT_PRIVATE_QUARANTINE", shape(Path("/var/lib/kmj-main-platform-rollback-quarantine")))
    emit("BACKUP_SERVICE", "NOT_MODIFIED")
    emit("PRODUCTION_RELEASE", "UNCHANGED")
    emit("STAGING_MUTATIONS", "NONE")
    emit("STAGING_PREP", "READ_ONLY_COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
