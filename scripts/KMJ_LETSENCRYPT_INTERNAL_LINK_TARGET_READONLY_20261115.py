#!/usr/bin/python3
"""KMJ TECHNO P0: metadata-only Let's Encrypt internal-link target proof.

Root-only --inspect on fixed KMJ-elite /etc/letsencrypt; no content reads,
no symlink traversal, no repair, no backup execution, no service mutation.
Verify every relative source-tree link resolves lexically within this root
to ONE directly reachable root-owned regular file via nofollow descriptors.
This is admission evidence, NOT permission to change the V3 backup builder.
"""
from __future__ import annotations
import os
from pathlib import Path
import posixpath
import socket
import stat
import sys
import tempfile

SOURCE = Path("/etc/letsencrypt")
EXPECTED_LINKS = 8
LIMIT_ENTRIES = 50000
LIMIT_DEPTH = 20
MAX_TARGET_BYTES = 1024 * 1024
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK

class Block(Exception):
    pass

def normalized_target(parent: str, text: str):
    if (not isinstance(text, str) or not text or len(text) > 1024
            or "\x00" in text or text.startswith("/")):
        raise Block("LINK_ABSOLUTE_OR_INVALID")
    dest = posixpath.normpath(posixpath.join(parent, text))
    if dest in ("", ".", "..") or dest.startswith("../"):
        raise Block("LINK_TARGET_ESCAPES_ROOT")
    parts = dest.split("/")
    if (len(parts) > LIMIT_DEPTH + 2
            or any(x in ("", ".", "..") or len(x) > 255 for x in parts)):
        raise Block("LINK_TARGET_PARTS_INVALID")
    return parts

def target_file(root_fd: int, parts: list[str], uid: int):
    fd = os.dup(root_fd)
    try:
        for name in parts[:-1]:
            nxt = os.open(name, DIR_FLAGS, dir_fd=fd)
            try:
                s = os.fstat(nxt)
                if (not stat.S_ISDIR(s.st_mode) or s.st_uid != uid
                        or (s.st_mode & 0o022)):
                    raise Block("TARGET_PARENT_UNTRUSTED")
            except BaseException:
                os.close(nxt)
                raise
            os.close(fd)
            fd = nxt
        out = os.open(parts[-1], FILE_FLAGS, dir_fd=fd)
        try:
            s = os.fstat(out)
            if (not stat.S_ISREG(s.st_mode) or s.st_uid != uid
                    or s.st_nlink != 1 or s.st_mode & 0o022
                    or not 1 <= s.st_size <= MAX_TARGET_BYTES):
                raise Block("TARGET_FILE_UNTRUSTED")
        finally:
            os.close(out)
    except OSError:
        raise Block("TARGET_NOSYMLINK_OPEN_FAILED") from None
    finally:
        os.close(fd)

def inspect_tree(root: Path, uid: int, expected: int = EXPECTED_LINKS):
    if type(expected) is not int or not 0 <= expected <= 64:
        raise Block("LINK_EXPECTATION_INVALID")
    fd = os.open(root, DIR_FLAGS)
    rootstat = os.fstat(fd)
    if (not stat.S_ISDIR(rootstat.st_mode) or rootstat.st_uid != uid
            or rootstat.st_mode & 0o022):
        os.close(fd)
        raise Block("ROOT_NOT_TRUSTED")
    counters = {"links": 0, "targets": 0, "special": 0, "regular": 0, "entries": 0}
    def visit(curr: int, parent: str, depth: int):
        if depth > LIMIT_DEPTH:
            raise Block("SOURCE_DEPTH_LIMIT")
        old = os.fstat(curr)
        if (old.st_uid != uid or old.st_mode & 0o022
                or not stat.S_ISDIR(old.st_mode)):
            raise Block("DIRECTORY_OWNER_OR_MODE_CHANGED")
        with os.scandir(curr) as rows:
            for child in rows:
                counters["entries"] += 1
                if counters["entries"] > LIMIT_ENTRIES:
                    raise Block("SOURCE_ENTRIES_LIMIT")
                name = child.name
                if (not isinstance(name, str) or not name or name in (".", "..")
                        or "/" in name or "\x00" in name or len(name) > 255):
                    raise Block("SOURCE_NAME_INVALID")
                st = os.stat(name, dir_fd=curr, follow_symlinks=False)
                if st.st_uid != uid:
                    raise Block("SOURCE_ENTRY_OWNER_MISMATCH")
                if stat.S_ISLNK(st.st_mode):
                    counters["links"] += 1
                    if counters["links"] > 64:
                        raise Block("TOO_MANY_LINKS")
                    value = os.readlink(name, dir_fd=curr)
                    parts = normalized_target(parent, value)
                    target_file(fd, parts, uid)
                    latest = os.stat(name, dir_fd=curr, follow_symlinks=False)
                    meta = lambda x: (x.st_dev, x.st_ino, x.st_mtime_ns, x.st_ctime_ns)
                    if meta(st) != meta(latest):
                        raise Block("LINK_CHANGED_DURING_CHECK")
                    counters["targets"] += 1
                elif stat.S_ISDIR(st.st_mode):
                    nxt = os.open(name, DIR_FLAGS, dir_fd=curr)
                    try:
                        now = os.fstat(nxt)
                        if (now.st_dev, now.st_ino) != (st.st_dev, st.st_ino):
                            raise Block("DIRECTORY_CHANGED_DURING_OPEN")
                        visit(nxt, posixpath.join(parent, name), depth + 1)
                    finally:
                        os.close(nxt)
                elif stat.S_ISREG(st.st_mode):
                    if st.st_mode & 0o022 or st.st_nlink != 1:
                        raise Block("SOURCE_REGULAR_FILE_UNTRUSTED")
                    counters["regular"] += 1
                else:
                    counters["special"] += 1
                    raise Block("SOURCE_SPECIAL_ENTRY")
        new = os.fstat(curr)
        if ((old.st_dev, old.st_ino, old.st_mtime_ns, old.st_ctime_ns)
                != (new.st_dev, new.st_ino, new.st_mtime_ns, new.st_ctime_ns)):
            raise Block("SOURCE_CHANGED_DURING_SCAN")
    try:
        visit(fd, "", 0)
        if counters["links"] != expected or counters["targets"] != expected:
            raise Block("LINK_COUNT_NOT_EXPECTED")
        return counters
    finally:
        os.close(fd)

def selftest():
    assert normalized_target("live/site", "../../archive/site/cert1.pem") == [
        "archive", "site", "cert1.pem"]
    for text in ("/etc/passwd", "../../../outside", "", "../../"):
        try: normalized_target("live/site", text)
        except Block: pass
        else: raise AssertionError("UNSAFE_LINK_ACCEPTED")
    with tempfile.TemporaryDirectory(prefix="kmj-link-proof-fixture-") as tmp:
        root = Path(tmp)
        (root/"archive").mkdir()
        (root/"archive"/"domain").mkdir()
        (root/"live").mkdir()
        (root/"live"/"domain").mkdir()
        (root/"archive"/"domain"/"cert1.pem").write_text("offline fixture only")
        (root/"live"/"domain"/"cert.pem").symlink_to("../../archive/domain/cert1.pem")
        x = inspect_tree(root, os.geteuid(), expected=1)
        assert x["links"] == x["targets"] == 1
        (root/"live"/"domain"/"danger").symlink_to("/etc/passwd")
        try: inspect_tree(root, os.geteuid(), expected=2)
        except Block: pass
        else: raise AssertionError("ABSOLUTE_LINK_ACCEPTED")
    print("KMJ_CERT_LINK_TARGET_SELFTEST=PASS")
    print("PRODUCTION_MUTATION=NONE")

def main():
    if sys.argv[1:] == ["--selftest"]:
        selftest()
        return 0
    if sys.argv[1:] != ["--inspect"]:
        print("RESULT=BLOCKED_ARGUMENT")
        return 2
    if os.geteuid() != 0 or socket.gethostname().split(".")[0] != "KMJ-elite":
        print("RESULT=BLOCKED_ROOT_HOST_REQUIRED")
        return 3
    try:
        x = inspect_tree(SOURCE, 0)
    except (Block, OSError, ValueError) as ex:
        code = str(ex)
        if code not in ("LINK_ABSOLUTE_OR_INVALID", "LINK_TARGET_ESCAPES_ROOT",
            "LINK_TARGET_PARTS_INVALID", "TARGET_PARENT_UNTRUSTED",
            "TARGET_FILE_UNTRUSTED", "TARGET_NOSYMLINK_OPEN_FAILED",
            "ROOT_NOT_TRUSTED", "SOURCE_DEPTH_LIMIT", "DIRECTORY_OWNER_OR_MODE_CHANGED",
            "SOURCE_ENTRIES_LIMIT", "SOURCE_NAME_INVALID", "SOURCE_ENTRY_OWNER_MISMATCH",
            "TOO_MANY_LINKS", "LINK_CHANGED_DURING_CHECK", "DIRECTORY_CHANGED_DURING_OPEN",
            "SOURCE_REGULAR_FILE_UNTRUSTED", "SOURCE_SPECIAL_ENTRY",
            "SOURCE_CHANGED_DURING_SCAN", "LINK_COUNT_NOT_EXPECTED"):
            code = "SOURCE_TREE_UNVERIFIED"
        print("BLOCKER=" + code)
        print("RESULT=BLOCKED_NO_MUTATION")
        return 3
    print("SCHEMA=KMJ_LETSENCRYPT_INTERNAL_LINK_TARGET_READONLY_V1")
    print("SOURCE_ENTRY_COUNT=" + str(x["entries"]))
    print("RELATIVE_LINKS=" + str(x["links"]))
    print("NONFOLLOW_ROOTED_REGULAR_TARGETS=" + str(x["targets"]))
    print("SPECIAL_ENTRIES=" + str(x["special"]))
    print("SOURCE_OR_TARGET_FILE_CONTENT_READ=NO")
    print("SOURCE_NAMES_LINK_VALUES_SECRETS_PRINTED=NO")
    print("BACKUP_AND_SERVICE_MUTATION=NONE")
    print("BUILDER_OR_PUBLISHER_MUTATION=NONE")
    print("INDEPENDENT_REMOTE_RESTORE=NOT_VERIFIED")
    print("RESULT=INTERNAL_CERT_TARGETS_METADATA_PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
