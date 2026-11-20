#!/usr/bin/env python3
"""Fail-closed, nonroot SHA256 sidecar verifier. No backup mutation or release approval."""
import argparse
import hashlib
import os
import re
import stat
import sys

HEX_LINE = re.compile(rb"([0-9a-f]{64})  ([A-Za-z0-9][A-Za-z0-9._-]*\.tar\.age)\n\Z")
FLAGS = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | os.O_NOFOLLOW | os.O_NONBLOCK

class Rejected(Exception):
    pass

def identity(st):
    return (st.st_dev, st.st_ino, st.st_mode, st.st_size, st.st_mtime_ns, st.st_ctime_ns)

def open_regular(parent_fd, name):
    fd = os.open(name, FLAGS, dir_fd=parent_fd)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_size == 0:
            raise Rejected("not a singly-linked regular file")
        return fd, st
    except BaseException:
        os.close(fd)
        raise

def open_parent(path):
    # Never normalize away dot segments before validating each ancestor.
    if not os.path.isabs(path):
        raise Rejected("absolute path required")
    parts = path.split(os.sep)
    if any(part in ("", ".", "..") for part in parts[1:]):
        raise Rejected("unsafe path component")
    fd = os.open(os.sep, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[1:-1]:
            if not part or part in (".", ".."):
                raise Rejected("unsafe path component")
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
        return fd, parts[-1]
    except BaseException:
        os.close(fd)
        raise

def verify(cipher_path, sidecar_path):
    # Freeze the pathname reference frame: cwd changes must not redirect a
    # final identity rewalk to another tree after the initial open.
    if not os.path.isabs(cipher_path) or not os.path.isabs(sidecar_path):
        raise Rejected("absolute paths required")
    if os.path.abspath(cipher_path) == os.path.abspath(sidecar_path):
        raise Rejected("same input")
    cparent, cname = open_parent(cipher_path)
    try:
        sparent, sname = open_parent(sidecar_path)
        try:
            # Reject same-basename sidecars supplied from another directory.
            cp, sp = os.fstat(cparent), os.fstat(sparent)
            if (cp.st_dev, cp.st_ino) != (sp.st_dev, sp.st_ino):
                raise Rejected("cipher and sidecar must share a directory")
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*\.tar\.age", cname):
                raise Rejected("unsafe ciphertext basename")
            if sname != cname + ".sha256":
                raise Rejected("sidecar path must match ciphertext basename")
            cfd, cst = open_regular(cparent, cname)
            try:
                sfd, sst = open_regular(sparent, sname)
                try:
                    if (cst.st_dev, cst.st_ino) == (sst.st_dev, sst.st_ino):
                        raise Rejected("same inode")
                    data = os.read(sfd, 4096)
                    if len(data) > 200 or os.read(sfd, 1):
                        raise Rejected("oversized sidecar")
                    match = HEX_LINE.fullmatch(data)
                    if not match or match.group(2).decode("ascii") != cname:
                        raise Rejected("noncanonical sidecar")
                    if identity(os.fstat(sfd)) != identity(sst):
                        raise Rejected("sidecar changed")
                    h = hashlib.sha256()
                    while True:
                        chunk = os.read(cfd, 1024 * 1024)
                        if not chunk:
                            break
                        h.update(chunk)
                    if identity(os.fstat(cfd)) != identity(cst):
                        raise Rejected("cipher changed")
                    if identity(os.fstat(sfd)) != identity(sst):
                        raise Rejected("sidecar changed")
                    # Refuse a swapped directory entry after opening either file.
                    if identity(os.stat(cname, dir_fd=cparent, follow_symlinks=False)) != identity(cst):
                        raise Rejected("cipher path swapped")
                    if identity(os.stat(sname, dir_fd=sparent, follow_symlinks=False)) != identity(sst):
                        raise Rejected("sidecar path swapped")
                    if h.hexdigest().encode("ascii") != match.group(1):
                        raise Rejected("SHA256 mismatch")
                    # Rewalk the original absolute path: an attacker may rename
                    # the parent directory while our open directory FD stays valid.
                    check_fd, check_name = open_parent(cipher_path)
                    try:
                        if check_name != cname or (os.fstat(check_fd).st_dev, os.fstat(check_fd).st_ino) != (cp.st_dev, cp.st_ino):
                            raise Rejected("cipher parent path swapped")
                        if identity(os.stat(check_name, dir_fd=check_fd, follow_symlinks=False)) != identity(cst):
                            raise Rejected("cipher entry swapped during final path rewalk")
                    finally:
                        os.close(check_fd)
                    check_fd, check_name = open_parent(sidecar_path)
                    try:
                        if check_name != sname or (os.fstat(check_fd).st_dev, os.fstat(check_fd).st_ino) != (sp.st_dev, sp.st_ino):
                            raise Rejected("sidecar parent path swapped")
                        if identity(os.stat(check_name, dir_fd=check_fd, follow_symlinks=False)) != identity(sst):
                            raise Rejected("sidecar entry swapped during final path rewalk")
                    finally:
                        os.close(check_fd)
                finally:
                    os.close(sfd)
            finally:
                os.close(cfd)
        finally:
            os.close(sparent)
    finally:
        os.close(cparent)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cipher")
    parser.add_argument("sidecar")
    args = parser.parse_args()
    try:
        verify(args.cipher, args.sidecar)
    except (OSError, Rejected, UnicodeError, ValueError) as exc:
        print("AGE_SIDECAR_VERIFY=FAIL", file=sys.stderr)
        return 1
    print("AGE_SIDECAR_VERIFY=PASS_LOCAL_DIGEST_ONLY")
    return 0

if __name__ == "__main__":
    sys.exit(main())
