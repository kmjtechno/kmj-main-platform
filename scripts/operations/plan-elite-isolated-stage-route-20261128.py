#!/usr/bin/env python3
"""Read-only exact staging route proposal. Never edits nginx or reloads services.

The output contains hashes and categorical results only. The proposed bytes
must undergo independent review and separate protected activation, including
actual FPM socket/DB/runtime qualification and rollback rehearsal.
"""
import argparse
import hashlib
import os
from pathlib import Path
import re
import socket
import stat

OLD = "a9796a25a2801cd303a69f5ad468aa9a704e5fff"
NEW = "710c6f3ca10310457bc7243caabc0e48476ec110"
BASE = "/var/lib/kmj-main-platform-stage-serving/"
OLD_SOCKET = "/run/php/kmjstage-a979-php84-fpm.sock"
NEW_SOCKET = "/run/php/kmjstage-710c6f3c-php84-fpm.sock"
ENABLED = Path("/etc/nginx/sites-enabled/staging.kmjtechno.com.conf")
AVAILABLE = Path("/etc/nginx/sites-available/staging.kmjtechno.com.conf")
LIVE = Path("/home/kmjprod/current")
LIVE_EXPECTED = Path("/home/kmjprod/releases/platform-72e7c9ada190")


def require(ok, label):
    if not ok:
        raise ValueError(label)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def proposal(raw):
    text = raw.decode("ascii")
    require("\r" not in text and "\x00" not in text, "UNSUPPORTED_CONFIG")
    # Only these three exact whole-line directives may be changed. Do not
    # parse arbitrary nginx syntax or accept embedded includes/variables here.
    old = (
        ("root", BASE + OLD + "/public"),
        ("fastcgi_param SCRIPT_FILENAME", BASE + OLD + "/code/public/index.php"),
        ("fastcgi_pass", "unix:" + OLD_SOCKET),
    )
    new = (
        BASE + NEW + "/public",
        BASE + NEW + "/code/public/index.php",
        "unix:" + NEW_SOCKET,
    )
    require(len(re.findall(r"(?m)^[ \t]*server_name[ \t]+staging\.kmjtechno\.com[ \t]*;[ \t]*$", text)) == 2,
            "STAGE_HOST_SCOPE")
    require(not re.search(r"(?im)^[ \t]*add_header[ \t]+X-KMJ-Deploy-SHA\b", text),
            "EXISTING_DEPLOY_HEADER")
    for (directive, value), replacement in zip(old, new):
        pattern = r"(?m)^([ \t]*)" + re.escape(directive) + r"[ \t]+" + re.escape(value) + r";[ \t]*$"
        matches = list(re.finditer(pattern, text))
        require(len(matches) == 1, "ROUTE_BASELINE_MISMATCH")
        match = matches[0]
        line = match.group(1) + directive + " " + replacement + ";"
        if directive == "root":
            # Proposal only: origin header is set by the staging server config,
            # not by an arbitrary application response. Inheritance and included
            # config still require validation on Elite before use.
            line += "\n" + match.group(1) + "add_header X-KMJ-Deploy-SHA " + NEW + " always;"
        text = text[:match.start()] + line + text[match.end():]
    require(OLD not in text and OLD_SOCKET not in text, "OLD_ROUTE_REFERENCES_REMAIN")
    return text.encode("ascii")


def read_config():
    for parent in (ENABLED.parent, AVAILABLE.parent, ENABLED.parent.parent):
        st = parent.lstat()
        require(stat.S_ISDIR(st.st_mode) and st.st_uid == 0 and not st.st_mode & 0o022,
                "UNTRUSTED_CONFIG_PARENT")
    if ENABLED.is_symlink():
        require(ENABLED.resolve(strict=True) == AVAILABLE, "CONFIG_LINK_SCOPE")
        path = AVAILABLE
    else:
        path = ENABLED
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    with os.fdopen(fd, "rb") as stream:
        st = os.fstat(stream.fileno())
        require(stat.S_ISREG(st.st_mode) and st.st_uid == 0 and st.st_nlink == 1
                and not st.st_mode & 0o022 and 0 < st.st_size <= 65536, "CONFIG_METADATA")
        data = stream.read(65537)
        after = os.fstat(stream.fileno())
        require(len(data) == st.st_size and (st.st_ino, st.st_mtime_ns, st.st_ctime_ns) ==
                (after.st_ino, after.st_mtime_ns, after.st_ctime_ns), "CONFIG_DRIFT")
        return data


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inspect", action="store_true", required=True)
    args = p.parse_args()
    try:
        require(os.geteuid() == 0 and socket.gethostname().split(".")[0].lower() == "kmj-elite", "HOST_ROOT")
        require(LIVE.is_symlink() and LIVE.resolve(strict=True) == LIVE_EXPECTED, "LIVE_POINTER_DRIFT")
        current = read_config()
        proposed = proposal(current)
        print("STAGE_ROUTE_BASELINE_SHA256=" + digest(current))
        print("STAGE_ROUTE_PROPOSAL_SHA256=" + digest(proposed))
        print("STAGE_ROUTE_PLAN=PASS_READ_ONLY")
        print("STAGE_ROUTE_ACTIVATION=NOT_ATTEMPTED")
        print("STAGING_ORIGIN_RECEIPT=NOT_ISSUED")
        print("PRODUCTION_POINTER=UNCHANGED")
        return 0
    except (OSError, ValueError, UnicodeError) as exc:
        print("STAGE_ROUTE_PLAN=BLOCKED_" + (str(exc) if isinstance(exc, ValueError) and re.fullmatch(r"[A-Z_]+", str(exc)) else "FILESYSTEM_OR_FORMAT"))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
