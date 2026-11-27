#!/usr/bin/python3
"""Owner root installer: replace the installed V3 dual-local health helper with the
reviewed and merged version (kmj-main-platform PR #1107, commit f4c2bf66).

What it does, in this order, and stops at the first failed check:
  1. root on KMJ-elite only; the unit is not running.
  2. the installed helper is exactly the old pinned file (bea4fcff...) and its .sha256
     file matches it; both are root-owned, one link, no group/other write.
  3. downloads the new helper from the pinned commit and requires exact SHA-256 and size.
  4. keeps a root-only backup of the old helper and old .sha256 next to them.
  5. replaces the helper, then its .sha256 file, each atomically.
  6. checks: sha256sum --check (the unit's own pre-start check), --selftest,
     --audit-pins and --preflight (read-only). On a failed check 6a/6b it restores the old files.

It never starts the service or the timer, never runs --run-once, never uploads,
never touches the health-check file, backups, keys, nginx, DNS or releases.
Output: one text file next to this script (symbolic lines only, no secrets).
"""
import hashlib
import os
import pathlib
import re
import socket
import stat
import subprocess
import sys
import time
import urllib.request

HOST = "KMJ-elite"
OWNER_UID = 0
LIB = pathlib.Path("/usr/local/libexec")
INSTALLED = LIB / "kmj-v3-dual-local-health-onepass-20261118.py"
SUMFILE = LIB / "kmj-v3-dual-local-health-onepass-20261118.sha256"
OLD_SHA = "bea4fcffefd369b8200628b860a8af7971b3143662a9566b1db8c5d2607ad650"
NEW_SHA = "35bc2414dc94ea252dcc0e29f82b5b3b51ec7a0ba5ba69312ee1064d4db44bf3"
NEW_SIZE = 29295
COMMIT = "f4c2bf668e4d72ddec324319378fe6883d46ad8e"
URL = ("https://raw.githubusercontent.com/kmjtechno/kmj-main-platform/" + COMMIT +
       "/scripts/KMJ_OFFSITE_V3_DUAL_LOCAL_HEALTH_ONEPASS_20261117.py")
UNIT = "kmj-v3-dual-local-health.service"
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C", "LANG": "C", "HOME": "/root"}
SYMBOLIC = re.compile(r"[A-Z0-9_]{3,80}=[A-Za-z0-9_.:+-]{1,80}\Z")
LINES = []


class Stop(Exception):
    pass


def say(text):
    LINES.append(text)
    print(text)


def need(condition, code):
    if not condition:
        raise Stop(code)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def trusted_read(path, limit=200000):
    st = os.lstat(path)
    need(stat.S_ISREG(st.st_mode) and st.st_uid == OWNER_UID and st.st_nlink == 1
         and not st.st_mode & 0o022, "INSTALLED_FILE_UNTRUSTED")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        data = os.read(fd, limit + 1)
    finally:
        os.close(fd)
    need(len(data) == st.st_size <= limit, "INSTALLED_FILE_SIZE_UNEXPECTED")
    return data


def run(cmd, timeout):
    return subprocess.run(cmd, cwd=str(LIB), env=ENV, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          timeout=timeout, check=False)


def symbolic(output):
    rows = []
    for row in output.decode("utf-8", "replace").splitlines():
        row = row.strip()
        if SYMBOLIC.fullmatch(row):
            rows.append(row)
    return rows


def environment_ok():
    need(os.geteuid() == 0, "ROOT_REQUIRED")
    need(socket.gethostname().split(".")[0] == HOST, "HOST_NOT_KMJ_ELITE")


def unit_idle():
    p = run(["/usr/bin/systemctl", "show", "--no-pager", "-p", "ActiveState", UNIT], 15)
    state = p.stdout.decode("ascii", "replace").strip()
    need(p.returncode == 0 and state in ("ActiveState=inactive", "ActiveState=failed"),
         "UNIT_NOT_IDLE")
    return state


def fetch_new():
    with urllib.request.urlopen(URL, timeout=30) as response:
        data = response.read(131073)
    need(len(data) == NEW_SIZE and sha(data) == NEW_SHA, "DOWNLOAD_SHA_OR_SIZE_MISMATCH")
    return data


def parse_sumfile(text):
    m = re.fullmatch(r"([0-9a-f]{64}) ([ *])(\S+)\n?", text)
    need(m is not None, "SUMFILE_FORMAT_UNEXPECTED")
    need(m.group(3) in (str(INSTALLED), INSTALLED.name), "SUMFILE_TARGET_UNEXPECTED")
    return m.group(1), m.group(2), m.group(3)


def write_new(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        os.fchmod(fd, 0o600)
        os.fchown(fd, 0, 0)
        view = memoryview(data)
        while view:
            done = os.write(fd, view)
            need(done > 0, "SHORT_WRITE")
            view = view[done:]
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_replace(path, data):
    tmp = path.with_name(path.name + ".new." + str(os.getpid()))
    write_new(tmp, data)
    os.replace(tmp, path)
    dfd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


def sum_check_passes():
    return run(["/usr/bin/sha256sum", "--check", "--status", str(SUMFILE)], 30).returncode == 0


def install():
    environment_ok()
    say("HOST=KMJ-elite")
    say("UNIT_" + unit_idle())
    old = trusted_read(INSTALLED)
    old_sum = trusted_read(SUMFILE, 4096)
    old_hash, sep, name = parse_sumfile(old_sum.decode("ascii"))
    need(sha(old) == old_hash, "INSTALLED_SUMFILE_MISMATCH")
    if sha(old) == NEW_SHA:
        need(sum_check_passes(), "ALREADY_NEW_BUT_SUM_CHECK_FAILS")
        say("RESULT=ALREADY_INSTALLED")
        return 0
    need(sha(old) == OLD_SHA, "INSTALLED_HELPER_NOT_THE_KNOWN_OLD_FILE")
    need(sum_check_passes(), "OLD_SUM_CHECK_FAILS_BEFORE_CHANGE")
    say("OLD_HELPER=PINNED_EXACT")
    new = fetch_new()
    say("NEW_HELPER_DOWNLOAD=SHA_AND_SIZE_EXACT")
    new_sum = (NEW_SHA + " " + sep + name + "\n").encode("ascii")

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    bak_py = INSTALLED.with_name(INSTALLED.name + ".bak." + stamp)
    bak_sum = SUMFILE.with_name(SUMFILE.name + ".bak." + stamp)
    write_new(bak_py, old)
    write_new(bak_sum, old_sum)
    say("BACKUP_OLD_HELPER_AND_SUMFILE=WRITTEN_ROOT_ONLY")

    def restore():
        atomic_replace(INSTALLED, old)
        atomic_replace(SUMFILE, old_sum)

    try:
        atomic_replace(INSTALLED, new)
        atomic_replace(SUMFILE, new_sum)
        need(sum_check_passes(), "NEW_SUM_CHECK_FAILED")
        p = run(["/usr/bin/python3", "-I", "-B", str(INSTALLED), "--selftest"], 60)
        need(p.returncode == 0 and b"OFFLINE_SELFTEST=PASS" in p.stdout, "NEW_SELFTEST_FAILED")
    except Exception as e:
        restore()
        code = str(e) if re.fullmatch(r"[A-Z0-9_]{5,64}", str(e)) else type(e).__name__.upper()
        say("BLOCKER=" + code)
        say("ROLLED_BACK=OLD_HELPER_AND_SUMFILE_RESTORED")
        say("RESULT=BLOCKED_ROLLED_BACK")
        return 3
    say("NEW_HELPER_INSTALLED=SHA_EXACT")
    say("UNIT_PRESTART_SUM_CHECK=PASS")
    say("NEW_HELPER_SELFTEST=PASS")

    audit = run(["/usr/bin/python3", "-I", "-B", str(INSTALLED), "--audit-pins"], 60)
    rows = symbolic(audit.stdout)
    for row in rows:
        say("AUDIT_" + row)
    audit_ok = audit.returncode == 0 and "HEALTH_SOURCE_PIN=PASS" in rows

    pre = run(["/usr/bin/python3", "-I", "-B", str(INSTALLED), "--preflight"], 180)
    for row in symbolic(pre.stdout):
        say("PREFLIGHT_" + row)
    say("PREFLIGHT_EXIT=" + str(pre.returncode))

    say("SERVICE_OR_TIMER_STARTED=NO")
    say("RUN_ONCE_EXECUTED=NO")
    say("HEALTH_CHECK_FILE_CHANGED=NO")
    say("RESULT=" + ("INSTALLED_AND_PIN_AUDIT_PASS" if audit_ok else "INSTALLED_PIN_AUDIT_NOT_PASS"))
    return 0


def main():
    try:
        return install()
    except Stop as e:
        say("BLOCKER=" + str(e))
        say("NOTHING_CHANGED_BEFORE_THIS_CHECK=YES")
        say("RESULT=BLOCKED_NO_CHANGE")
        return 3
    except Exception as e:
        say("BLOCKER=" + type(e).__name__.upper())
        say("RESULT=BLOCKED_CHECK_STATE")
        return 3


def write_report():
    here = pathlib.Path(__file__).resolve().parent
    out = here / "V3_HELPER_INSTALL_20261124.txt"
    out.write_text("\n".join(LINES) + "\n")
    try:
        owner = here.stat().st_uid
        os.chown(out, owner, -1)
        os.chmod(out, 0o640)
    except OSError:
        pass
    print("WROTE " + str(out))


if __name__ == "__main__":
    code = main()
    write_report()
    raise SystemExit(code)
