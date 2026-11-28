#!/usr/bin/env python3
"""Per-release rehearsal workspace: copies of the PREVIOUS and CANDIDATE code trees
and a DISPOSABLE PostgreSQL database, plus the root-protected config the rollback
rehearsal collector reads (source only until installed).

  --write   <sha> <expected-release>   create workspace, database, config
  --cleanup <sha> <expected-release>   drop database and role, delete workspace and config

Safety properties:
  * identity comes from the argv the runner derives from the protected approval;
  * trees are copied WITHOUT any .env file, cached config, storage tree or symlink,
    so the rehearsal can never read production secrets or reach shared storage;
  * database name/role are derived from the SHA, match the rehearsal's own
    disposable-name pattern, are loopback-only, non-superuser, and stamped with a
    random nonce comment the rehearsal independently checks;
  * only names matching the fixed pattern are ever dropped; production databases,
    the live pointer, approvals and releases are never touched.
"""
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import release_admission_receipts as ra  # noqa: E402

BASE = Path("/var/lib/kmj-release-rehearsal")
CONFIG = Path("/etc/kmj-codebridge/release-rehearsal.json")
PREV_ROOT = Path("/home/kmjprod/releases")
CAND_ROOT = Path("/home/kmjstage/releases")
OWNER = "kmjprod"
NAME_RE = re.compile(r"kmj_rehearsal_[0-9a-f]{12}\Z")
# Order matters for rsync: the single allowed .env.example comes before the .env* exclusion.
FILTERS = (("--include", ".env.example"), ("--exclude", ".env*"),
           ("--exclude", "/bootstrap/cache/*.php"), ("--exclude", "/storage/**"),
           ("--exclude", "/public/storage"), ("--exclude", "/node_modules/"),
           ("--exclude", "/.git/"))


def names(sha):
    name = "kmj_rehearsal_" + sha[:12]
    assert NAME_RE.fullmatch(name)
    return name


def tree_paths(sha, expected):
    return (PREV_ROOT / expected / "apps" / "platform",
            CAND_ROOT / sha / "apps" / "platform")


def sql_create(name, password, nonce):
    for value, pattern in ((name, NAME_RE), (password, re.compile(r"[0-9a-f]{32}\Z")),
                           (nonce, re.compile(r"[0-9a-f]{32}\Z"))):
        if not pattern.fullmatch(value):
            raise ValueError("BLOCKED_UNSAFE_SQL_INPUT")
    return [
        'DROP DATABASE IF EXISTS "{n}" WITH (FORCE)'.format(n=name),
        'DROP ROLE IF EXISTS "{n}"'.format(n=name),
        "CREATE ROLE \"{n}\" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD '{p}'".format(n=name, p=password),
        'CREATE DATABASE "{n}" OWNER "{n}"'.format(n=name),
        "COMMENT ON DATABASE \"{n}\" IS 'kmj-disposable-rehearsal:{x}'".format(n=name, x=nonce),
    ]


def sql_drop(name):
    if not NAME_RE.fullmatch(name):
        raise ValueError("BLOCKED_UNSAFE_SQL_INPUT")
    return ['DROP DATABASE IF EXISTS "{n}" WITH (FORCE)'.format(n=name),
            'DROP ROLE IF EXISTS "{n}"'.format(n=name)]


def rsync_argv(src, dst):
    argv = ["/usr/bin/rsync", "-a", "--no-links", "--delete"]
    for flag, pattern in FILTERS:
        argv += [flag, pattern]
    return argv + [str(src) + "/", str(dst) + "/"]


def make_config(name, password, nonce, prev, cand):
    return {"env": {
        "DB_DATABASE": name, "DB_USERNAME": name, "DB_PASSWORD": password,
        "DB_HOST": "127.0.0.1", "DB_PORT": "5432",
        "KMJ_REHEARSAL_PREVIOUS_APP": str(prev), "KMJ_REHEARSAL_CANDIDATE_APP": str(cand),
        "KMJ_REHEARSAL_DB_NONCE": nonce,
    }}


def real_tree(path, root):
    """A genuine directory under its release root, no symlink anywhere on the way."""
    if not path.is_dir() or path.resolve(strict=True) != path or root not in path.parents:
        return False
    return all((path / f).is_file() for f in ("artisan", "vendor/autoload.php", "public/index.php"))


def run(argv, user=None):
    cmd = (["/usr/sbin/runuser", "-u", user, "--"] if user else []) + argv
    out = subprocess.run(cmd, cwd="/", env={"PATH": "/usr/bin:/bin", "LANG": "C"},
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
                         timeout=1800)
    if out.returncode != 0:
        raise ValueError("BLOCKED_STEP_FAILED")


def psql(sql_list):
    for sql in sql_list:
        run(["/usr/bin/psql", "-X", "-v", "ON_ERROR_STOP=1", "-d", "postgres", "-c", sql], "postgres")


def write_config(config, path=CONFIG):
    tmp = path.with_name("." + path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(json.dumps(config, sort_keys=True))
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def prepare(sha, expected, runner=run, sql_runner=psql, base=BASE, config_path=CONFIG,
            check_trees=real_tree):
    prev, cand = tree_paths(sha, expected)
    if not (check_trees(prev, PREV_ROOT) and check_trees(cand, CAND_ROOT)):
        raise ValueError("BLOCKED_TREE_UNTRUSTED_OR_MISSING")
    name = names(sha)
    work = base / sha[:12]
    cleanup(sha, runner, sql_runner, base, config_path)
    work.mkdir(parents=True, mode=0o700)
    for label, src in (("previous", prev), ("candidate", cand)):
        runner(rsync_argv(src, work / label))
    runner(["/usr/bin/chown", "-R", OWNER + ":" + OWNER, str(work)])
    password, nonce = secrets.token_hex(16), secrets.token_hex(16)
    sql_runner(sql_create(name, password, nonce))
    write_config(make_config(name, password, nonce, work / "previous", work / "candidate"),
                 config_path)


def cleanup(sha, runner=run, sql_runner=psql, base=BASE, config_path=CONFIG):
    name = names(sha)
    sql_runner(sql_drop(name))
    work = base / sha[:12]
    if work.exists():
        if work.is_symlink() or work.resolve(strict=True).parent != base.resolve(strict=True):
            raise ValueError("BLOCKED_WORKDIR_UNTRUSTED")
        shutil.rmtree(work)
    try:
        config_path.unlink()
    except FileNotFoundError:
        pass


def main(argv):
    if len(argv) != 4 or argv[1] not in ("--write", "--cleanup"):
        print("usage: --write|--cleanup <40-hex-sha> <platform-12hex>")
        return 2
    sha, expected = argv[2], argv[3]
    if not ra.SHA_RE.fullmatch(sha) or not ra.RELEASE_RE.fullmatch(expected):
        print("REHEARSAL_WORKSPACE=BLOCKED_INPUT")
        return 2
    if os.geteuid() != 0 or socket.gethostname().split(".")[0] != "KMJ-elite":
        print("REHEARSAL_WORKSPACE=BLOCKED_OPERATOR_HOST")
        return 2
    try:
        if argv[1] == "--write":
            prepare(sha, expected)
        else:
            cleanup(sha)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print("REHEARSAL_WORKSPACE=FAIL REASON=" + type(exc).__name__ + ":" + str(exc)[:60])
        return 1
    print("REHEARSAL_WORKSPACE=" + ("READY" if argv[1] == "--write" else "CLEANED"))
    print("PRODUCTION_DATABASE_TOUCHED=NO PRODUCTION_RELEASE=NOT_ATTEMPTED APPROVAL_UPDATED=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
