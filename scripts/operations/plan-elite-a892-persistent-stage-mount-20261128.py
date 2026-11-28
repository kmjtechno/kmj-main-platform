#!/usr/bin/env python3
"""Plan a candidate-only persistent shared-storage bind mount.

Read-only inspection, no unit installation, enable, mount, daemon reload,
candidate edit, route change, or approval. The actual mount installer must
independently revalidate this exact plan under the staging lock.
"""
import hashlib
import os
from pathlib import Path
import re
import stat
import subprocess

SHA = "a892b0d5d851129a9d8ed00c1af1390da6ee584f"
RELEASE = Path("/home/kmjstage/releases") / SHA
APP = RELEASE / "apps/platform"
TARGET = APP / "storage/app"
SOURCE = Path("/home/kmjstage/shared/storage-app-b2e69decab3a")
ARTWORK = Path("/home/kmjstage/shared/product-artwork")
STAGE = Path("/home/kmjstage/htdocs/staging.kmjtechno.com")
PROD = Path("/home/kmjprod/current")
STAGE_OLD = Path("/home/kmjstage/releases/b2e69decab3acd861e94e11992cd8a4cff4f2b94/apps/platform")
PROD_OLD = Path("/home/kmjprod/releases/platform-457481eb652f")
ENV = {"PATH":"/usr/sbin:/usr/bin:/sbin:/bin","LANG":"C","GIT_OPTIONAL_LOCKS":"0"}


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def cmd(args):
    p = subprocess.run(args, env=ENV, cwd="/", capture_output=True, timeout=30)
    need(p.returncode == 0, "COMMAND_FAILED")
    return p.stdout.decode("utf-8", "strict").strip()


def protected_dir(path):
    for p in (path, *path.parents):
        s = p.lstat()
        need(stat.S_ISDIR(s.st_mode) and s.st_uid == 0 and not s.st_mode & 0o022,
             "ROOT_PARENT_SCOPE")


def unit_bytes():
    # Deliberately not RequiredBy=php8.4-fpm.service: production uses
    # that service too. A future candidate-specific serving unit must
    # require this mount and verify its source identity before admission.
    return (
        "[Unit]\n"
        "Description=KMJ exact a892 staging shared storage\n"
        "[Mount]\n"
        f"What={SOURCE}\n"
        f"Where={TARGET}\n"
        "Type=none\n"
        "Options=bind,nosuid,nodev,noexec\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    ).encode("ascii")


def main():
    import socket
    need(os.geteuid()==0 and socket.gethostname().split(".")[0]=="KMJ-elite","HOST_ROOT")
    protected_dir(TARGET.parent)
    protected_dir(Path("/etc/systemd/system"))
    need(TARGET.is_symlink() and TARGET.resolve(strict=True)==SOURCE,"SHARED_LINK_SCOPE")
    need(SOURCE.is_dir() and not SOURCE.is_symlink() and SOURCE.resolve(strict=True)==SOURCE,
         "SOURCE_SCOPE")
    artwork=SOURCE/"private/product-artwork"
    need(artwork.is_symlink() and artwork.resolve(strict=True)==ARTWORK,"ARTWORK_SCOPE")
    need(STAGE.is_symlink() and STAGE.resolve(strict=True)==STAGE_OLD,"STAGE_DRIFT")
    need(PROD.is_symlink() and PROD.resolve(strict=True)==PROD_OLD,"PRODUCTION_DRIFT")
    name=cmd(["/usr/bin/systemd-escape","--path","--suffix=mount",str(TARGET)])
    need(re.fullmatch(r"[A-Za-z0-9_.\\-]+\.mount",name) is not None,"UNIT_NAME")
    for directory in ("/etc/systemd/system","/run/systemd/system","/usr/lib/systemd/system",
                      "/lib/systemd/system"):
        need(not os.path.lexists(Path(directory)/name),"UNIT_EXISTS")
    need(not os.path.lexists(Path("/etc/systemd/system/multi-user.target.wants")/name),
         "ENABLE_LINK_EXISTS")
    # No persistent competing fstab rule, including its systemd generated units.
    fstab=Path("/etc/fstab").read_text("utf-8")
    for line in fstab.splitlines():
        cols=line.split("#",1)[0].split()
        if len(cols)>=2:
            need(cols[1]!=str(TARGET),"FSTAB_CONFLICT")
    for directory in ("/run/systemd/generator","/run/systemd/generator.early",
                      "/run/systemd/generator.late"):
        need(not os.path.lexists(Path(directory)/name),"GENERATED_UNIT_EXISTS")
    # A 000 root-owned underlying mountpoint is planned, not installed.
    # Candidate-specific admission also needs a live mount identity check.
    print("STORAGE_SOURCE_IDENTITY=PASS")
    print("PERSISTENT_MOUNT_UNIT="+name)
    print("MOUNT_UNIT_SHA256="+hashlib.sha256(unit_bytes()).hexdigest())
    print("MOUNT_OPTIONS=bind,nosuid,nodev,noexec")
    print("UNDERLYING_MOUNTPOINT_MODE=000_PLANNED")
    print("PRODUCTION_FPM_DEPENDENCY_CHANGE=NONE")
    print("CANDIDATE_RUNTIME_MOUNT_GUARD=REQUIRED")
    print("PERSISTENT_MOUNT_PLAN=PASS_READ_ONLY")
    print("INSTALLATION=NOT_ATTEMPTED")
    print("SECRET_OUTPUT=NONE")


if __name__=="__main__":
    try:
        main()
    except (OSError,ValueError,subprocess.SubprocessError) as e:
        print("PERSISTENT_MOUNT_PLAN=BLOCKED_"+(str(e) if isinstance(e,ValueError)
              and re.fullmatch(r"[A-Z_]+",str(e)) else type(e).__name__))
        raise SystemExit(2)
