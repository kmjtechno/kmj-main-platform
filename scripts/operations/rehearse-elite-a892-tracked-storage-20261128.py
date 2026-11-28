#!/usr/bin/env python3
"""Exact a892 private-mount-namespace tracked storage rehearsal.

Does not change candidate files, shared files, the host mount table, nginx,
systemd, approval or either release pointer. Only a private temporary worktree
is used. Success is a layout feasibility proof, not persistent mount approval.
"""
import argparse
import hashlib
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile

SHA = "a892b0d5d851129a9d8ed00c1af1390da6ee584f"
RELEASE = Path("/home/kmjstage/releases") / SHA
APP = RELEASE / "apps/platform"
SHARED = Path("/home/kmjstage/shared/storage-app-b2e69decab3a")
ARTWORK = Path("/home/kmjstage/shared/product-artwork")
APP_STORAGE = APP / "storage/app"
VIEWS_IGNORE = APP / "storage/framework/views/.gitignore"
FILES = {
    "apps/platform/storage/app/.gitignore": "fedb287fece8049b6bd243804b133e3af7a43f4c",
    "apps/platform/storage/app/private/.gitignore": "d6b7ef32c8478a48c3994dcadc86837f4371184d",
    "apps/platform/storage/app/public/.gitignore": "d6b7ef32c8478a48c3994dcadc86837f4371184d",
    "apps/platform/storage/framework/views/.gitignore": "d6b7ef32c8478a48c3994dcadc86837f4371184d",
}
ENV = {"PATH":"/usr/sbin:/usr/bin:/sbin:/bin","LANG":"C",
       "GIT_OPTIONAL_LOCKS":"0","GIT_CONFIG_GLOBAL":"/dev/null","GIT_CONFIG_NOSYSTEM":"1"}


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def blob(raw):
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()


def call(args, timeout=30):
    p = subprocess.run(args, env=ENV, cwd="/", capture_output=True, timeout=timeout)
    need(p.returncode == 0, "COMMAND_FAILED")
    return p.stdout


def git(*args, worktree=RELEASE):
    return call(["/usr/bin/git", "-c", "safe.directory="+str(RELEASE),
                 "-c","core.fsmonitor=false","-c","core.filemode=true",
                 "--git-dir="+str(RELEASE/".git"),"--work-tree="+str(worktree), *args])


def exact_dir(path):
    s = path.lstat()
    need(stat.S_ISDIR(s.st_mode) and path.resolve(strict=True)==path, "DIRECTORY_SCOPE")
    return s


def placeholder(path, expected):
    fd = os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    with os.fdopen(fd,"rb") as f:
        s = os.fstat(f.fileno())
        need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and not s.st_mode&0o111 and
             0 < s.st_size <= 256, "PLACEHOLDER_METADATA")
        raw = f.read(257)
        t = os.fstat(f.fileno())
        need((s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)==
             (t.st_dev,t.st_ino,t.st_size,t.st_mtime_ns,t.st_ctime_ns) and
             blob(raw)==expected,"PLACEHOLDER_CONTENT")
    return raw


def baseline():
    need(git("rev-parse","HEAD").strip()==SHA.encode(),"HEAD_SCOPE")
    # The full tracked inventory must be exactly the four reported deletions.
    changes = git("diff","--name-status","--no-renames","-z","HEAD","--").split(b"\0")
    need(changes[-1:]==[b""] and len(changes)==9, "UNEXPECTED_TRACKED_CHANGES")
    need({(changes[i].decode(),changes[i+1].decode()) for i in range(0,8,2)}==
         {("D",p) for p in FILES},"UNEXPECTED_TRACKED_CHANGES")
    need(APP_STORAGE.is_symlink() and APP_STORAGE.resolve(strict=True)==SHARED,"SHARED_LINK_SCOPE")
    exact_dir(SHARED)
    for p in ("private","public"):
        exact_dir(SHARED/p)
    a=SHARED/"private/product-artwork"
    need(a.is_symlink() and a.resolve(strict=True)==ARTWORK,"ARTWORK_SCOPE")
    need(not os.path.lexists(VIEWS_IGNORE),"VIEWS_PLACEHOLDER_PRESENT")
    source={}
    for rel,pin in FILES.items():
        raw=git("show",SHA+":"+rel)
        need(blob(raw)==pin,"GIT_BLOB_PIN")
        source[rel]=raw
        if "/storage/app/" in rel:
            path=SHARED/Path(rel).relative_to("apps/platform/storage/app")
            need(placeholder(path,pin)==raw,"SHARED_PLACEHOLDER_DRIFT")
    return source


def main():
    import socket
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private",action="store_true",required=True)
    p.parse_args()
    need(os.geteuid()==0 and socket.gethostname().split(".")[0]=="KMJ-elite","HOST_ROOT")
    # The launcher is required to provide a new mount namespace. Refuse the
    # ordinary host mount namespace even if the process is root.
    need(os.stat("/proc/self/ns/mnt").st_ino!=os.stat("/proc/1/ns/mnt").st_ino,
         "HOST_MOUNT_NAMESPACE")
    # Ensure a bind mount cannot propagate back to the parent namespace.
    call(["/usr/bin/mount","--make-rprivate","/"])
    source=baseline()
    # Do NOT use automatic recursive temporary-directory cleanup: if a
    # bind unmount fails it could traverse the shared source. Leave the
    # scratch directory behind on any mount/unmount ambiguity.
    tree=Path(tempfile.mkdtemp(prefix="kmj-stage-mount-rehearsal-",dir="/run"))
    mounted=False
    try:
        target=tree/"apps/platform/storage/app"
        target.mkdir(parents=True)
        view=tree/"apps/platform/storage/framework/views/.gitignore"
        view.parent.mkdir(parents=True)
        view.write_bytes(source[str(VIEWS_IGNORE.relative_to(RELEASE))])
        try:
            call(["/usr/bin/mount","--bind",str(SHARED),str(target)])
            mounted=True
            # Rehearsal uses read-only bind remount; the host source's mount
            # and permissions are unchanged in this private namespace.
            call(["/usr/bin/mount","-o","remount,bind,ro",str(target)])
            x,y=SHARED.stat(),target.stat()
            need((x.st_dev,x.st_ino)==(y.st_dev,y.st_ino),"BIND_IDENTITY")
            need((target/"private/product-artwork").resolve(strict=True)==ARTWORK,"ARTWORK_IDENTITY")
            need(not git("diff","--name-status","--no-renames","HEAD","--",*FILES,worktree=tree),
                 "TRACKED_PLACEHOLDER_DIFF")
            print("PRIVATE_BIND_IDENTITY=PASS")
            print("TRACKED_PLACEHOLDER_REHEARSAL=PASS")
            print("SHARED_ARTWORK_CONTINUITY=PASS")
        finally:
            if mounted:
                call(["/usr/bin/umount",str(target)])
                mounted=False
    finally:
        # Even a timed-out mount command can have completed. Check the
        # actual mount table before cleanup; do not recurse into a mount.
        if not mounted and not os.path.ismount(tree/"apps/platform/storage/app"):
            # Remove only our known file and empty scratch directories.
            # No recursive deletion of any kind.
            view=tree/"apps/platform/storage/framework/views/.gitignore"
            if view.is_file() and not view.is_symlink():
                view.unlink()
            for rel in ("apps/platform/storage/framework/views","apps/platform/storage/framework",
                        "apps/platform/storage/app","apps/platform/storage",
                        "apps/platform","apps",""):
                d=tree/rel
                if d.is_dir():
                    d.rmdir()
    need(baseline()==source,"BASELINE_DRIFT")
    print("HOST_MOUNT_CHANGED=NO")
    print("CANDIDATE_MODIFIED=NO")
    print("PERSISTENT_MOUNT=NOT_INSTALLED")
    print("STORAGE_LAYOUT_REHEARSAL=PASS")
    print("SECRET_OUTPUT=NONE")


if __name__=="__main__":
    try:
        main()
    except (OSError,ValueError,subprocess.SubprocessError) as e:
        print("STORAGE_LAYOUT_REHEARSAL=BLOCKED_"+(str(e) if isinstance(e,ValueError)
              and re.fullmatch(r"[A-Z_]+",str(e)) else type(e).__name__))
        raise SystemExit(2)
