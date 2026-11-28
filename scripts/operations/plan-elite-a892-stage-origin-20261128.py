#!/usr/bin/env python3
"""Read-only exact staging origin proposal; never writes nginx or activates.

This is not a database choice, migration authorization, or origin receipt.
The current stage mirror and the populated legacy DB remain separate.
"""
import hashlib
import os
from pathlib import Path
import re
import socket
import stat
import subprocess

OLD = "457481eb652f92cfa016aee022f43fe64c4396b3"
NEW = "a892b0d5d851129a9d8ed00c1af1390da6ee584f"
LEGACY = "b2e69decab3acd861e94e11992cd8a4cff4f2b94"
MIRROR = "/var/lib/kmj-main-platform-stage-serving/" + OLD
APP = Path("/home/kmjstage/releases") / NEW / "apps/platform"
OLD_SOCKET = "/run/php/kmjstage-457481eb-php84-fpm.sock"
NEW_SOCKET = "/run/php/kmjstage-php84-fpm.sock"
ENABLED = Path("/etc/nginx/sites-enabled/staging.kmjtechno.com.conf")
AVAILABLE = Path("/etc/nginx/sites-available/staging.kmjtechno.com.conf")
PROD = Path("/home/kmjprod/current")
PROD_EXPECTED = Path("/home/kmjprod/releases/platform-457481eb652f")
STAGE = Path("/home/kmjstage/htdocs/staging.kmjtechno.com")
STAGE_EXPECTED = Path("/home/kmjstage/releases") / LEGACY / "apps/platform"
REMOTE = "https://github.com/kmjtechno/kmj-main-platform.git"
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG":"C",
       "HOME":"/root", "GIT_CONFIG_GLOBAL":"/dev/null",
       "GIT_CONFIG_NOSYSTEM":"1", "GIT_TERMINAL_PROMPT":"0"}


def need(ok, label):
    if not ok:
        raise ValueError(label)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def proposal(raw):
    text = raw.decode("ascii")
    need("\r" not in text and "\x00" not in text, "CONFIG_FORMAT")
    need(len(re.findall(r"(?m)^[ \t]*server_name[ \t]+staging\.kmjtechno\.com[ \t]*;[ \t]*$", text)) == 2,
         "STAGING_HOST_SCOPE")
    # Refuse unreviewed storage mapping or header override; never inject an
    # origin attestation header solely to make HTTP qualification pass.
    need(not re.search(r"(?im)^[ \t]*(?:add_header|more_set_headers)[^\n]*X-KMJ-Deploy-SHA", text),
         "EXISTING_DEPLOY_HEADER")
    need(not re.search(r"(?im)^[ \t]*location[^\n{]*?/storage(?:[/ \t{]|$)", text),
         "STORAGE_ROUTE_REQUIRES_REVIEW")
    changes = [
        ("root", MIRROR + "/public", str(APP / "public")),
        ("fastcgi_param SCRIPT_FILENAME", MIRROR + "/code/public/index.php", str(APP / "public/index.php")),
        ("fastcgi_pass", "unix:" + OLD_SOCKET, "unix:" + NEW_SOCKET),
    ]
    for directive, old, new in changes:
        pattern = r"(?m)^([ \t]*)" + re.escape(directive) + r"[ \t]+" + re.escape(old) + r";[ \t]*$"
        matches = list(re.finditer(pattern, text))
        need(len(matches) == 1, "ROUTE_BASELINE_MISMATCH")
        m = matches[0]
        text = text[:m.start()] + m.group(1) + directive + " " + new + ";" + text[m.end():]
    need(MIRROR not in text and OLD_SOCKET not in text, "OLD_ROUTE_REMAINS")
    need(len(re.findall(r"(?m)^[ \t]*location[ \t]+=[ \t]+/register[ \t]*\{[ \t]*return[ \t]+403;[ \t]*\}", text)) == 2,
         "REGISTER_DENIAL_SCOPE")
    # Never add an alias, weaken PHP locations, or alter unrelated directives.
    return text.encode("ascii")


def protected_chain(path):
    for p in (path, *path.parents):
        s = p.lstat()
        need(stat.S_ISDIR(s.st_mode) and s.st_uid == 0 and not s.st_mode & 0o022,
             "UNTRUSTED_PARENT")


def protected_read(path, limit):
    protected_chain(path.parent)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(fd, "rb") as f:
        s = os.fstat(f.fileno())
        need(stat.S_ISREG(s.st_mode) and s.st_uid == 0 and s.st_nlink == 1
             and not s.st_mode & 0o022 and 0 < s.st_size <= limit, "FILE_METADATA")
        data = f.read(limit + 1)
        def fp(x):
            return x.st_dev,x.st_ino,x.st_size,x.st_mode,x.st_mtime_ns,x.st_ctime_ns
        need(len(data) == s.st_size and fp(s) == fp(os.fstat(f.fileno()))
             and fp(s) == fp(path.lstat()), "FILE_DRIFT")
    return data


def check_pointers():
    need(STAGE.is_symlink() and os.readlink(STAGE) == str(STAGE_EXPECTED)
         and STAGE.resolve(strict=True) == STAGE_EXPECTED, "STAGE_POINTER_DRIFT")
    need(PROD.is_symlink() and os.readlink(PROD) in
         {str(PROD_EXPECTED), "releases/" + PROD_EXPECTED.name}
         and PROD.resolve(strict=True) == PROD_EXPECTED, "PRODUCTION_POINTER_DRIFT")


def command(args):
    p = subprocess.run(args, env=ENV, cwd="/root", capture_output=True, timeout=30)
    need(p.returncode == 0, "COMMAND_FAILED")
    return p.stdout


def main():
    need(os.geteuid() == 0 and socket.gethostname().split(".")[0] == "KMJ-elite", "HOST_ROOT")
    check_pointers()
    protected_chain(ENABLED.parent)
    need(ENABLED.is_symlink() and ENABLED.resolve(strict=True) == AVAILABLE, "NGINX_LINK_SCOPE")
    before = protected_read(AVAILABLE, 65536)
    after = proposal(before)
    protected_chain(APP / "public/build")
    attestation = protected_read(APP / "public/build/.kmj-deploy-sha", 41)
    need(attestation in (NEW.encode(), (NEW+"\n").encode()), "DEPLOY_ATTESTATION")
    need(stat.S_ISSOCK(os.lstat(NEW_SOCKET).st_mode) and stat.S_ISSOCK(os.lstat(OLD_SOCKET).st_mode),
         "SOCKET_SCOPE")
    refs = command(["/usr/bin/git","ls-remote","--exit-code",REMOTE,
                    "refs/heads/main","refs/heads/staging-approved"])
    need(set(refs.decode().splitlines()) == {NEW+"\trefs/heads/main",NEW+"\trefs/heads/staging-approved"},
         "SOURCE_DRIFT")
    command(["/usr/sbin/nginx","-t"])
    check_pointers()
    need(protected_read(AVAILABLE,65536) == before, "CONFIG_DRIFT")
    print("STAGE_ROUTE_BASELINE_SHA256="+digest(before))
    print("STAGE_ROUTE_PROPOSAL_SHA256="+digest(after))
    print("DEPLOY_ATTESTATION=PASS")
    print("STAGE_ROUTE_PLAN=PASS_READ_ONLY")
    print("PUBLIC_STORAGE_MAPPING=NOT_QUALIFIED")
    print("DATABASE_CHOICE=NOT_AUTHORIZED_BY_PLAN")
    print("STAGE_ROUTE_ACTIVATION=NOT_ATTEMPTED")
    print("PRODUCTION_POINTER=UNCHANGED")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        print("STAGE_ROUTE_PLAN=BLOCKED_"+(str(e) if isinstance(e,ValueError)
              and re.fullmatch(r"[A-Z_]+",str(e)) else type(e).__name__))
        raise SystemExit(2)
