#!/usr/bin/python3
"""KMJ-elite guarded offsite service transport migration.

The exact known legacy executable is reused for local encrypted backup creation,
except its final two remote ssh/rsync commands. Those commands are deliberately
NEVER executed. The new encrypted artifact is sent over the already approved,
strictly pinned, restricted SFTP transport. No production app or SSH identity
is modified. --apply mutates ONLY the failing backup unit, with rollback.
"""
from __future__ import annotations

import datetime
import hashlib
import os
from pathlib import Path
import re
import secrets
import socket
import stat
import subprocess
import sys
import tempfile

UNIT = "kmj-elite-offsite-backup.service"
LEGACY = Path("/usr/local/sbin/kmj-elite-offsite-backup")
LEGACY_SHA = "d66fd2c2cc33c53c1d0a82f1c259640ee642b666feb2c4aaee6cf887dfe98848"
VAULT = Path("/var/backups/kmj-elite-offsite-encrypted")
CONFIG = Path("/etc/kmj-codebridge/offsite-sftp.conf")
IDENTITY = Path("/root/.ssh/kmj-google-offsite-20261031-ed25519")
HOST = "34.63.5.14"
PORT = "22"
USER = "info"
REMOTE = "/home/info/kmj-recovery-scratch"
PIN = "SHA256:9ibmOwHchvHmaLTDNv8Osm0IIepfZNnQY+BMF7CuJWU"
CLIENT_PIN = "SHA256:JIvb33Ca2dAD+/1xbXnbQAg18zIZhjczxQoLPnyIIWk"
CONF = (f"HOST={HOST}\nPORT={PORT}\nUSER={USER}\nREMOTE_DIR={REMOTE}\n"
        f"IDENTITY_FILE={IDENTITY}\nHOSTKEY_SHA256={PIN}\n").encode("ascii")
REPAIR_FILE = Path("/usr/local/libexec/kmj-elite-offsite-sftp-repair.py")
DROPIN_DIR = Path("/etc/systemd/system/kmj-elite-offsite-backup.service.d")
DROPIN = DROPIN_DIR / "90-kmj-pinned-sftp-repair.conf"
DROPIN_TEXT = ("[Service]\nExecStart=\n"
               "ExecStart=/usr/bin/python3 -I -B " + str(REPAIR_FILE) + " --run\n")
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "HOME": "/root", "LC_ALL": "C", "LANG": "C"}
MAX_SOURCE = 1048576
MAX_CIPHER = 8 * (1024 ** 3)


class Block(Exception):
    pass


def emit(key: str, value: str) -> None:
    if not re.fullmatch(r"[A-Z][A-Z0-9_]+", key) or not re.fullmatch(r"[A-Z0-9_.:-]+", value):
        raise Block("INTERNAL_OUTPUT_REJECTED")
    print(f"{key}={value}", flush=True)


def protected_chain(path: Path) -> None:
    parent = path.parent
    while True:
        meta = os.lstat(parent)
        if not stat.S_ISDIR(meta.st_mode) or meta.st_uid != 0 or meta.st_mode & 0o022:
            raise Block("UNSAFE_PARENT")
        if parent == Path("/"):
            break
        parent = parent.parent


def read_private(path: Path, limit: int, mode: int = 0o022) -> bytes:
    protected_chain(path)
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
    try:
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != 0 or before.st_nlink != 1
                or before.st_mode & mode or not 1 <= before.st_size <= limit):
            raise Block("UNSAFE_FILE")
        result = os.read(fd, limit + 1)
        after = os.fstat(fd)
        if (len(result) != before.st_size or
                (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) !=
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
            raise Block("RACED_FILE")
        return result
    finally:
        os.close(fd)


def check_legacy() -> bytes:
    data = read_private(LEGACY, MAX_SOURCE)
    if hashlib.sha256(data).hexdigest() != LEGACY_SHA:
        raise Block("LEGACY_SHA_DRIFT")
    return data


def fixed_prefix(raw: bytes) -> bytes:
    """Preserve exact local recipe and exclude ONLY direct last-two SSH commands.

    The user attested that the known SHA's non-comment lines 29 and 30 are ssh
    and rsync, after archive creation, encryption, move and checksum. Refuse
    even a harmless source change until reviewed; no heuristic shell patching.
    """
    if b"\x00" in raw or b"\r" in raw:
        raise Block("LEGACY_NOT_CANONICAL_BASH")
    lines = raw.splitlines(keepends=True)
    if len(lines) < 30:
        raise Block("LEGACY_TOO_SHORT")
    nonempty = [(i + 1, x.decode("utf-8", "strict").strip())
                for i, x in enumerate(lines) if x.strip() and not x.lstrip().startswith(b"#")]
    if len(nonempty) < 2 or nonempty[-2][0] != 29 or nonempty[-1][0] != 30:
        raise Block("LEGACY_TAIL_NOT_EXACT")
    if not re.fullmatch(r"(?:/usr/bin/)?ssh(?:[ \t].*)?", nonempty[-2][1]):
        raise Block("LEGACY_SSH_NOT_DIRECT")
    if not re.fullmatch(r"(?:/usr/bin/)?rsync(?:[ \t].*)?", nonempty[-1][1]):
        raise Block("LEGACY_RSYNC_NOT_DIRECT")
    if lines[27].rstrip(b"\n").endswith(b"\\"):
        raise Block("LEGACY_PREFIX_CONTINUED_INTO_SSH")
    prefix = b"".join(lines[:28])
    if not prefix.endswith(b"\n"):
        raise Block("LEGACY_PREFIX_NEWLINE")
    content = prefix.decode("utf-8", "strict")
    for row in content.splitlines():
        clean = row.lstrip()
        if clean.startswith("#"):
            continue
        if ("BASH_SOURCE" in clean
                or re.search(r"\$(?:\{?0\}?)", clean)
                or re.search(r"(?<![A-Za-z0-9_/-])(?:eval|source|ssh|rsync|scp)(?=[ \t])", clean)):
            raise Block("LEGACY_PREFIX_UNEXPECTED_CONTROL")
    syntax = call(["/bin/bash", "-n"], input_data=prefix, timeout=10)
    if syntax.returncode != 0:
        raise Block("LEGACY_PREFIX_SYNTAX")
    return prefix


def tail_shape_report(raw: bytes) -> dict[str, str]:
    """Metadata-only pinned legacy recipe shape. Never return shell text.

    This is not a waiver to the guarded apply preflight; the latter must still
    independently prove precisely which local lines are safe to execute.
    """
    if b"\x00" in raw or b"\r" in raw:
        raise Block("TAIL_NONCANONICAL_BYTES")
    lines = raw.decode("utf-8", "strict").splitlines()
    if not 30 <= len(lines) <= 5000:
        raise Block("TAIL_LINE_COUNT_UNEXPECTED")

    def active(line: str) -> bool:
        stripped = line.strip()
        return bool(stripped) and not stripped.startswith("#")

    def label(line: str, verb: str) -> str:
        item = line.strip()
        if not item:
            return "BLANK"
        if item.startswith("#"):
            return "COMMENT"
        if re.match(r"^(?:/usr/bin/)?"+verb+r"(?=\s|$)", item):
            return "DIRECT_" + verb.upper()
        if re.match(r"^(?:if|then|fi|for|while|do|done|case|esac|function|else|elif)\b", item):
            return "SHELL_CONTROL"
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", item):
            return "VARIABLE_ASSIGNMENT"
        if re.search(r"\b"+verb+r"\b", item):
            return "EMBEDDED_" + verb.upper()
        return "OTHER"

    noncomment = [i + 1 for i, value in enumerate(lines) if active(value)]
    after30 = [i for i in noncomment if i > 30]
    result = {
        "TAIL_SOURCE_SHA": "PASS",
        "TAIL_TOTAL_LINES": str(len(lines)),
        "TAIL_LAST_ACTIVE_LINE": str(noncomment[-1]) if noncomment else "0",
        "TAIL_LAST_TWO_ACTIVE": "_".join(map(str, noncomment[-2:])) if len(noncomment) >= 2 else "NONE",
        "TAIL_AFTER_LINE30_ACTIVE_COUNT": str(len(after30)),
        "TAIL_AFTER_LINE30_COMMENT_COUNT": str(sum(1 for row in lines[30:] if row.strip().startswith("#"))),
        "TAIL_LINE28_CONTINUES": "YES" if lines[27].rstrip().endswith("\\") else "NO",
        "TAIL_LINE29_CONTINUES": "YES" if lines[28].rstrip().endswith("\\") else "NO",
        "TAIL_LINE30_CONTINUES": "YES" if lines[29].rstrip().endswith("\\") else "NO",
        "TAIL_LINE29_SHAPE": label(lines[28], "ssh"),
        "TAIL_LINE30_SHAPE": label(lines[29], "rsync"),
        "TAIL_LINE29_HAS_SSH": "YES" if re.search(r"\bssh\b", lines[28]) else "NO",
        "TAIL_LINE30_HAS_RSYNC": "YES" if re.search(r"\brsync\b", lines[29]) else "NO",
        "TAIL_PREFIX_HAS_REMOTE_VERBS": "YES" if any(
            active(row) and re.search(r"(?<![A-Za-z0-9_-])(?:ssh|rsync|scp)\b", row)
            for row in lines[:28]) else "NO",
        "TAIL_DIAGNOSTIC_IS_EXECUTION_PROOF": "NO",
        "TAIL_AUTOMATIC_REPAIR_ALLOWED": "NO",
    }
    return result


def tail_review() -> None:
    """Owner-only read-only classification; no service/SSH/backup action."""
    report = tail_shape_report(check_legacy())
    for key, value in report.items():
        emit(key, value)
    emit("UNIT_MUTATION", "NONE")
    emit("SERVICE_EXECUTION", "NOT_RUN")


def call(argv: list[str], *, input_data: bytes | None = None, timeout: int = 40) -> subprocess.CompletedProcess:
    try:
        process = subprocess.run(argv, input=input_data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 cwd="/", env=ENV, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise Block("TOOL_FAILED_OR_TIMED_OUT") from None
    if len(process.stdout) > 65536 or len(process.stderr) > 65536:
        raise Block("TOOL_OUTPUT_OVERSIZE")
    return process


def prop(name: str) -> str | None:
    if name not in ("LoadState", "User", "Type", "DropInPaths", "ExecStart", "ActiveState",
                    "Result", "ExecMainStatus", "InvocationID"):
        raise Block("UNAPPROVED_PROPERTY")
    p = call(["/usr/bin/systemctl", "show", UNIT, f"--property={name}", "--value", "--no-pager"], timeout=10)
    return p.stdout.decode("utf-8", "replace").strip() if p.returncode == 0 else None


def unit_preflight(*, original: bool) -> None:
    if prop("LoadState") != "loaded" or prop("User") not in ("", "root"):
        raise Block("UNIT_USER_OR_LOAD_DRIFT")
    if prop("Type") != "oneshot":
        raise Block("UNIT_TYPE_NOT_ONESHOT")
    if original:
        if prop("DropInPaths") != "":
            raise Block("UNREVIEWED_DROPIN")
        expected = str(LEGACY)
    else:
        if prop("DropInPaths") != str(DROPIN):
            raise Block("INSTALLED_DROPIN_MISMATCH")
        expected = "/usr/bin/python3"
    start = prop("ExecStart") or ""
    matches = re.findall(r"\bpath=([^ ;]+)", start)
    if len(matches) != 1 or matches[0] != expected:
        raise Block("UNIT_EXECSTART_DRIFT")
    if prop("ActiveState") not in ("inactive", "failed"):
        raise Block("UNIT_ALREADY_RUNNING")


def pinned_conf() -> None:
    if read_private(CONFIG, 4096, mode=0o077) != CONF:
        raise Block("PINNED_CONFIG_DRIFT")
    read_private(IDENTITY, 16384, mode=0o077)
    public = call(["/usr/bin/ssh-keygen", "-y", "-P", "", "-f", str(IDENTITY)], timeout=12)
    if public.returncode != 0:
        raise Block("PRIVATE_KEY_UNAVAILABLE")
    with tempfile.TemporaryDirectory(prefix="kmj-ssh-public-", dir="/run") as root:
        pub = Path(root) / "pub"
        pub.write_bytes(public.stdout)
        pub.chmod(0o600)
        fp = call(["/usr/bin/ssh-keygen", "-lf", str(pub), "-E", "sha256"])
        if fp.returncode != 0 or len(fp.stdout.split()) < 2 or fp.stdout.split()[1].decode() != CLIENT_PIN:
            raise Block("CLIENT_FINGERPRINT_DRIFT")


def host_key() -> str:
    scan = call(["/usr/bin/ssh-keyscan", "-T", "15", "-t", "ed25519", "-p", PORT, HOST], timeout=25)
    if scan.returncode != 0:
        raise Block("HOSTKEY_SCAN_FAILED")
    lines = [x for x in scan.stdout.decode("ascii", "strict").splitlines() if x and not x.startswith("#")]
    if len(lines) != 1 or not lines[0].startswith(HOST + " ssh-ed25519 "):
        raise Block("HOSTKEY_SCAN_UNEXPECTED")
    with tempfile.TemporaryDirectory(prefix="kmj-ssh-pin-", dir="/run") as root:
        f = Path(root) / "known"
        f.write_text(lines[0] + "\n", encoding="ascii")
        f.chmod(0o600)
        fp = call(["/usr/bin/ssh-keygen", "-lf", str(f), "-E", "sha256"])
    if fp.returncode != 0 or len(fp.stdout.split()) < 2 or fp.stdout.split()[1].decode() != PIN:
        raise Block("HOSTKEY_PIN_MISMATCH")
    return lines[0] + "\n"


def sftp_argv(known: Path, batch: Path) -> list[str]:
    return ["/usr/bin/sftp", "-F", "/dev/null", "-b", str(batch), "-P", PORT,
            "-i", str(IDENTITY), "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
            "-o", "IdentityAgent=none", "-o", "PreferredAuthentications=publickey",
            "-o", "PasswordAuthentication=no", "-o", "KbdInteractiveAuthentication=no",
            "-o", "GSSAPIAuthentication=no", "-o", "ProxyCommand=none",
            "-o", "StrictHostKeyChecking=yes", "-o", "UpdateHostKeys=no",
            "-o", "HostKeyAlgorithms=ssh-ed25519", "-o", "GlobalKnownHostsFile=/dev/null",
            "-o", "UserKnownHostsFile=" + str(known), "-o", "ConnectTimeout=15",
            "-o", "ConnectionAttempts=1", "--", USER + "@" + HOST]


def sftp(known: Path, batch: Path, instructions: str, *, timeout: int = 100) -> None:
    if not instructions.isascii():
        raise Block("SFTP_BATCH_NOT_ASCII")
    batch.write_text(instructions, encoding="ascii")
    batch.chmod(0o600)
    result = call(sftp_argv(known, batch), timeout=timeout)
    if result.returncode != 0:
        raise Block("PINNED_SFTP_COMMAND_FAILED")


def vault_list() -> dict[str, tuple[int, int]]:
    protected_chain(VAULT / "object")
    v = os.lstat(VAULT)
    if not stat.S_ISDIR(v.st_mode) or v.st_uid != 0 or v.st_mode & 0o022:
        raise Block("VAULT_DIR_UNSAFE")
    result = {}
    for entry in os.scandir(VAULT):
        if not entry.name.endswith(".age"):
            continue
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,160}\.age", entry.name):
            raise Block("VAULT_NAME_INVALID")
        meta = entry.stat(follow_symlinks=False)
        if not stat.S_ISREG(meta.st_mode) or meta.st_uid != 0 or meta.st_nlink != 1:
            raise Block("VAULT_OBJECT_UNSAFE")
        result[entry.name] = (meta.st_dev, meta.st_ino)
        if len(result) > 2000:
            raise Block("VAULT_TOO_MANY_OBJECTS")
    return result


def digest_cipher(path: Path) -> str:
    protected_chain(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0))
    h = hashlib.sha256()
    try:
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != 0 or before.st_nlink != 1
                or before.st_mode & 0o077 or not 60 <= before.st_size <= MAX_CIPHER):
            raise Block("CIPHER_NOT_PROTECTED")
        if os.read(fd, 22) != b"age-encryption.org/v1\n":
            raise Block("NOT_AGE_CIPHERTEXT")
        os.lseek(fd, 0, os.SEEK_SET)
        while True:
            part = os.read(fd, 1024 * 1024)
            if not part:
                break
            h.update(part)
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
            raise Block("CIPHER_CHANGED_DURING_READ")
    finally:
        os.close(fd)
    return h.hexdigest()


def transfer(path: Path, expected: str, hostline: str) -> None:
    random_name = "kmj-legacy-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(16)
    partial, final = random_name + ".partial", random_name + ".age"
    space = os.statvfs(VAULT)
    bytes_free = space.f_bavail * space.f_frsize
    ciphertext_size = path.stat().st_size
    if bytes_free < ciphertext_size + 256 * 1024 * 1024:
        raise Block("READBACK_DISK_SPACE_INSUFFICIENT")
    with tempfile.TemporaryDirectory(prefix=".kmj-offsite-send-", dir=str(VAULT)) as name:
        tmp = Path(name)
        known, batch, copy = tmp / "known", tmp / "batch", tmp / "readback.age"
        known.write_text(hostline, encoding="ascii")
        known.chmod(0o600)
        sftp(known, batch, "pwd\n" + "cd " + REMOTE + "\n")
        emit("SSH_AUTH", "PASS")
        # Match the existing reviewed uploader: prove remote hard-link
        # support with a tiny object before spending bytes on the archive.
        probe = tmp / "probe"
        probe.write_bytes(b"kmj-offsite-sftp-link-probe\n")
        probe.chmod(0o600)
        pa, pb = ".probe-" + random_name, ".probe-" + random_name + ".ln"
        try:
            sftp(known, batch, f"cd {REMOTE}\nput {probe} {pa}\nln {pa} {pb}\nrm {pb}\nrm {pa}\n", timeout=50)
        except (Block, OSError):
            try:
                sftp(known, batch, f"cd {REMOTE}\n-rm {pb}\n-rm {pa}\n", timeout=25)
            except (Block, OSError):
                pass
            raise
        try:
            sftp(known, batch, f"cd {REMOTE}\nput -p {path} {partial}\nchmod 600 {partial}\nget -p {partial} {copy}\n", timeout=240)
            if digest_regular_download(copy) != expected:
                raise Block("CIPHER_READBACK_MISMATCH")
            # SFTP 'ln' creates the final name exclusively (EEXIST fails).
            # Never use 'rename', which could overwrite an existing archive.
            sftp(known, batch, f"cd {REMOTE}\nln {partial} {final}\n", timeout=45)
            sftp(known, batch, f"cd {REMOTE}\nrm {partial}\nget -p {final} {copy}\n", timeout=240)
            if digest_regular_download(copy) != expected:
                raise Block("FINAL_CIPHER_READBACK_MISMATCH")
        except (Block, OSError):
            try:
                sftp(known, batch, f"cd {REMOTE}\n-rm {partial}\n", timeout=30)
            except (Block, OSError):
                pass
            raise
    emit("OFFSITE_TRANSFER", "PASS")
    emit("SHA256_READBACK", "PASS")


def digest_regular_download(path: Path) -> str:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        st = os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1
                or stat.S_IMODE(st.st_mode) != 0o600
                or not 60 <= st.st_size <= MAX_CIPHER):
            raise Block("BAD_DOWNLOAD_OR_REMOTE_MODE")
        h = hashlib.sha256()
        while True:
            part = os.read(fd, 1024 * 1024)
            if not part:
                break
            h.update(part)
        return h.hexdigest()
    finally:
        os.close(fd)


def run_job() -> int:
    raw = check_legacy()
    prefix = fixed_prefix(raw)
    pinned_conf()
    hk = host_key()
    emit("HOSTKEY_PIN", "PASS")
    before = vault_list()
    with tempfile.TemporaryDirectory(prefix="kmj-legacy-backup-", dir="/run") as scratch:
        file = Path(scratch) / "local-prefix.sh"
        file.write_bytes(prefix)
        file.chmod(0o600)
        backup_env = os.environ.copy()
        for poison in ("BASH_ENV", "ENV", "CDPATH", "LD_PRELOAD", "LD_LIBRARY_PATH",
                       "GIT_DIR", "GIT_WORK_TREE", "PYTHONPATH", "PYTHONHOME"):
            backup_env.pop(poison, None)
        backup_env["PATH"] = ENV["PATH"]
        try:
            result = subprocess.run(["/bin/bash", "-p", str(file)], cwd="/", env=backup_env,
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=900, check=False)
        except (OSError, subprocess.TimeoutExpired):
            raise Block("LOCAL_BACKUP_TIMEOUT_OR_TOOL") from None
        if result.returncode != 0:
            raise Block("LOCAL_BACKUP_PREFIX_FAILED")
    after = vault_list()
    fresh = [name for name, ident in after.items() if before.get(name) != ident]
    if len(fresh) != 1:
        raise Block("FRESH_ENCRYPTED_BACKUP_COUNT_NOT_ONE")
    path = VAULT / fresh[0]
    expected = digest_cipher(path)
    emit("LOCAL_AGE_ENCRYPTED_ARCHIVE", "PASS")
    transfer(path, expected, hk)
    emit("BACKUP_OFFSITE", "PASS")
    emit("INDEPENDENT_RESTORE", "NOT_VERIFIED")
    emit("REMOTE_RETENTION", "NOT_VERIFIED")
    return 0


def _protected_write(path: Path, body: bytes, mode: int) -> None:
    protected_chain(path)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW
    fd = os.open(path, flags, mode)
    try:
        written = os.write(fd, body)
        if written != len(body):
            raise Block("INSTALL_FILE_SHORT_WRITE")
        os.fchmod(fd, mode)
        os.fsync(fd)
    finally:
        os.close(fd)


def verify_exact_service_receipt() -> None:
    """Tie evidence to the new systemd invocation, not a separate SFTP test."""
    inv = prop("InvocationID")
    if not inv or re.fullmatch(r"[0-9a-f]{32}", inv) is None:
        raise Block("SERVICE_INVOCATION_UNAVAILABLE")
    receipt = call(["/usr/bin/journalctl", "--no-pager", "--output=cat",
                    "--lines=200", "_SYSTEMD_INVOCATION_ID=" + inv], timeout=15)
    if receipt.returncode != 0:
        raise Block("SERVICE_JOURNAL_UNAVAILABLE")
    values = set(receipt.stdout.decode("utf-8", "replace").splitlines())
    required = ("HOSTKEY_PIN=PASS", "SSH_AUTH=PASS",
                "LOCAL_AGE_ENCRYPTED_ARCHIVE=PASS", "OFFSITE_TRANSFER=PASS",
                "SHA256_READBACK=PASS", "BACKUP_OFFSITE=PASS")
    if not set(required).issubset(values):
        raise Block("SERVICE_INDEPENDENT_RECEIPT_MISSING")
    for item in required:
        print(item, flush=True)


def setup_install() -> None:
    check_legacy()
    fixed_prefix(check_legacy())
    unit_preflight(original=True)
    pinned_conf()
    os.makedirs(REPAIR_FILE.parent, mode=0o755, exist_ok=True)
    os.makedirs(DROPIN_DIR, mode=0o755, exist_ok=True)
    if REPAIR_FILE.exists() or DROPIN.exists() or REPAIR_FILE.is_symlink() or DROPIN.is_symlink():
        raise Block("REPAIR_ALREADY_PRESENT")
    local = Path(__file__)
    code = read_private(local, MAX_SOURCE)
    if not code.startswith(b"#!/usr/bin/python3\n"):
        raise Block("INSTALL_SOURCE_UNEXPECTED")
    _protected_write(REPAIR_FILE, code, 0o500)
    try:
        _protected_write(DROPIN, DROPIN_TEXT.encode("ascii"), 0o644)
        reload = call(["/usr/bin/systemctl", "daemon-reload"], timeout=30)
        if reload.returncode != 0:
            raise Block("DAEMON_RELOAD_FAILED")
        start = call(["/usr/bin/systemctl", "start", UNIT], timeout=1000)
        if (start.returncode != 0 or prop("Result") != "success"
                or prop("ExecMainStatus") != "0"):
            raise Block("SERVICE_EXECUTION_FAILED")
        verify_exact_service_receipt()
        emit("SERVICE_EXECUTION", "PASS")
        emit("EXIT_255", "RESOLVED_FOR_REPAIRED_SERVICE")
    except (OSError, Block):
        if prop("ActiveState") not in ("inactive", "failed"):
            emit("ROLLBACK", "NEEDS_OWNER_REVIEW")
            raise
        try:
            if DROPIN.is_file() and not DROPIN.is_symlink() and DROPIN.read_bytes() == DROPIN_TEXT.encode("ascii"):
                DROPIN.unlink()
                restored = call(["/usr/bin/systemctl", "daemon-reload"], timeout=30)
                if restored.returncode != 0:
                    raise Block("ROLLBACK_DAEMON_RELOAD_FAILED")
        except (OSError, Block):
            emit("ROLLBACK", "NEEDS_OWNER_REVIEW")
        else:
            emit("ROLLBACK", "DROPIN_REVERTED")
        raise


def rollback_installed() -> None:
    """Only reverse this exact backup unit's reviewed drop-in, never run legacy."""
    if prop("ActiveState") not in ("inactive", "failed"):
        raise Block("ROLLBACK_SERVICE_STILL_ACTIVE")
    if (DROPIN.is_symlink() or not DROPIN.is_file()
            or read_private(DROPIN, 4096) != DROPIN_TEXT.encode("ascii")):
        raise Block("ROLLBACK_DROPIN_NOT_OURS")
    DROPIN.unlink()
    result = call(["/usr/bin/systemctl", "daemon-reload"], timeout=30)
    if result.returncode != 0:
        raise Block("ROLLBACK_RELOAD_FAILED")
    emit("ROLLBACK", "REVIEWED_DROPIN_REMOVED")
    emit("SERVICE_EXECUTION", "NOT_RUN")
    emit("LEGACY_RESTORED", "YES_NO_START")


def check_mode() -> None:
    """Stage-identified, redacted and strictly read-only host preflight."""
    raw = check_legacy()
    emit("PREFLIGHT_LEGACY_SOURCE", "PASS")
    fixed_prefix(raw)
    emit("PREFLIGHT_PREFIX_SYNTAX", "PASS")
    observed_type = prop("Type")
    if observed_type in ("oneshot", "simple", "exec", "forking", "notify"):
        emit("PREFLIGHT_UNIT_TYPE", observed_type.upper())
    else:
        emit("PREFLIGHT_UNIT_TYPE", "UNKNOWN")
    unit_preflight(original=True)
    emit("PREFLIGHT_UNIT_INVARIANTS", "PASS")
    pinned_conf()
    emit("PREFLIGHT_PINNED_CONFIG", "PASS")
    emit("SYSTEMD_SCOPE", "FAIL_CLOSED_REVIEWED")
    emit("UNIT_MUTATION", "NONE")
    emit("SERVICE_EXECUTION", "NOT_RUN")


def main() -> int:
    if (len(sys.argv) != 2 or sys.argv[1] not in ("--inspect", "--tail-review", "--run", "--apply", "--rollback")
            or os.geteuid() != 0 or socket.gethostname().split(".")[0] != "KMJ-elite"):
        emit("LEGACY_SFTP_REPAIR", "BLOCKED_OWNER_OR_ARGUMENTS")
        return 2
    try:
        if sys.argv[1] == "--inspect":
            check_mode()
        elif sys.argv[1] == "--tail-review":
            tail_review()
        elif sys.argv[1] == "--apply":
            setup_install()
        elif sys.argv[1] == "--rollback":
            rollback_installed()
        else:
            run_job()
    except Block as exc:
        # Block reasons are source-coded enums, never raw paths/SSH/journal.
        # Keep sensitive OSError content out of stdout and service journals.
        reason = str(exc)
        if re.fullmatch(r"[A-Z][A-Z0-9_]{2,63}", reason) is None:
            reason = "UNCLASSIFIED_GATE"
        emit("PRECHECK_BLOCKER", reason)
        emit("LEGACY_SFTP_REPAIR", "BLOCKED_OR_UNVERIFIED")
        return 3
    except (OSError, ValueError, UnicodeError):
        emit("PRECHECK_BLOCKER", "SANITIZED_LOCAL_ERROR")
        emit("LEGACY_SFTP_REPAIR", "BLOCKED_OR_UNVERIFIED")
        return 3
    status = {"--run": "PASS", "--apply": "INSTALL_PASS",
              "--inspect": "INSPECT_PASS", "--tail-review": "TAIL_READONLY_COMPLETE",
              "--rollback": "ROLLBACK_PASS"}
    emit("LEGACY_SFTP_REPAIR", status[sys.argv[1]])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
