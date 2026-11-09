"""Exact 09e8/bce410 guarded READ-ONLY native writer-scope inventory.

Adapted from the reviewed CD958 native read-only inventory; old CD958 release
identity and argv SHA pins are not inherited. No mutation adapter, application
bootstrap, execution of candidate PHP, or arbitrary paths. Any error remains
unverified. This does not establish writer quiescence or authorization to
switch storage or change protected approval.
"""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shlex
import socket
import stat
import subprocess

# Fixed target geometry: live storage is ALREADY shared; only candidate is local.
LIVE = "/home/kmjprod/releases/platform-bce4100d005e"
CANDIDATE_SHA = "09e8a224cd37445c42588a073a6b52d207475a09"
CANDIDATE = "/home/kmjprod/releases/platform-09e8a224cd37"
SHARED = "/home/kmjprod/shared/storage"
RELEASE_LOCK = "/run/lock/kmj-main-platform-production-release.lock"
PINS = {
    "helper": "72fe5702c59599bd1b28b88dad808dda5d6be97b61f0db06dc3a7295258a51b6",
    "scanner": "f4d01f6e3b40c9ad774c8ada5129b241cee93dac782ce75bb0e229b26bbc95ba",
    "materializer": "fd29c4ebcf224c45786f8cedd0e0d42bbfd414d706678fe820e0ead4eea3984f",
}
UNITS = ("kmj-main-platform-queue.service", "kmj-main-platform-scheduler.service",
         "kmj-main-platform-scheduler.timer")


class Blocked(RuntimeError):
    pass


def require(value, reason):
    if not value:
        raise Blocked(reason)


DEPENDENCIES = {
    "helper": "/usr/local/libexec/kmj-codebridge/main-platform-storage-snapshot-attest.py",
    "scanner": "/usr/local/libexec/kmj-codebridge/main-platform-storage-switch-v6.py",
}
MATERIALIZER_SOURCE = "/srv/kmj-codebridge-projects/kmj-main-platform/scripts/operations/materialize-main-platform-candidate-runtime.sh"
WORKER_HASH = "5eb06f601fa559565b98f6e84e9ca8eff9335e1d9d7a3dca25fcb214c499a617"
FRAMEWORK_REF = "7c75fbf93f91fa077d3df1c820cc14f4e59a9774"
# Old CD958 invocation hashes are deliberately NOT reused for a different
# production release. Need fresh owner-reviewed binding after inspecting
# authoritative current systemd ExecStart, before any writer drain.
EXPECTED_ARGV_HASHES = {"queue": "", "scheduler": ""}
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "HOME": "/nonexistent", "LC_ALL": "C"}
SERVICE_PROPERTIES = ("ActiveState", "SubState", "Type", "User", "Group", "MainPID", "ExecStart",
              "WorkingDirectory", "ControlGroup", "Restart", "KillMode", "TimeoutStopUSec", "Triggers", "TriggeredBy")
TIMER_PROPERTIES = ("ActiveState", "SubState", "Triggers")


def property_names(unit):
    return TIMER_PROPERTIES if unit == UNITS[2] else SERVICE_PROPERTIES
APP = Path(LIVE) / "apps/platform"
POOL = "kmj-elite-stage"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_file(path, limit=1048576, protected=False):
    """Read fixed files without following their final symlink; bind stable bytes."""
    path = Path(path)
    if protected:
        require(str(path) == os.path.realpath(path), "DEPENDENCY_PATH_UNSAFE")
        for parent in path.parents:
            info = parent.lstat()
            require(stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022,
                    "DEPENDENCY_PARENT_UNSAFE")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_size <= limit, "FILE_UNSAFE")
        if protected:
            require(before.st_uid == 0 and before.st_nlink == 1 and not before.st_mode & 0o022,
                    "DEPENDENCY_UNSAFE")
        chunks, length = [], 0
        while length <= limit:
            part = os.read(fd, min(65536, limit + 1 - length))
            if not part:
                break
            chunks.append(part); length += len(part)
        after = os.fstat(fd)
        stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        require(length <= limit and stamp(before) == stamp(after), "FILE_CHANGED_OR_TOO_LARGE")
        return b"".join(chunks)
    finally:
        os.close(fd)


def command(args):
    # Every caller below supplies fixed system tools and fixed read/test options.
    allowed = (args in (["/usr/sbin/nft", "-j", "list", "ruleset"],
                        ["/usr/sbin/php-fpm8.4", "-tt"], ["/usr/sbin/nginx", "-T"])
               or (len(args) == 5 and args[:2] == ["/usr/bin/systemctl", "show"]
                   and args[2] in (*UNITS, "php8.4-fpm.service", "nginx.service")
                   and args[3:] == ["--all", "--property=" + ",".join(property_names(args[2]))]))
    require(allowed, "NON_INVENTORY_COMMAND_REJECTED")
    executable = Path(args[0]).resolve(strict=True)
    read_file(executable, 64 * 1048576, protected=True)
    result = subprocess.run([str(executable), *args[1:]], stdin=subprocess.DEVNULL,
                            capture_output=True, timeout=25, check=True, env=ENV)
    require(len(result.stdout) + len(result.stderr) <= 8 * 1048576, "COMMAND_OUTPUT_TOO_LARGE")
    return result.stdout, result.stderr


def section(action):
    try:
        return {"observed": True, "data": action()}
    except (OSError, ValueError, KeyError, StopIteration, TypeError, IndexError, AttributeError,
            subprocess.SubprocessError, Blocked):
        # Never echo exceptions, command output, paths from configs or environment.
        return {"observed": False, "reason": "UNVERIFIED"}


def namespace(pid="self"):
    value = os.stat(f"/proc/{pid}/ns/net")
    return [value.st_dev, value.st_ino]


def process(pid):
    base = Path("/proc") / str(pid)
    raw = (base / "stat").read_text()
    fields = raw[raw.rfind(")") + 2:].split()
    uids = [int(x) for x in next(x for x in (base / "status").read_text().splitlines()
                                  if x.startswith("Uid:")).split()[1:]]
    args = [os.fsdecode(x) for x in (base / "cmdline").read_bytes().split(b"\0") if x]
    exe = os.readlink(base / "exe")
    cwd = os.readlink(base / "cwd")
    return {"pid": pid, "ppid": int(fields[1]), "start": int(fields[19]), "uids": uids,
            "args": args, "exe": exe, "cwd": cwd, "netns": namespace(pid)}


def argv_evidence(args, executable, cwd, expected_command, label):
    artisan = None
    if len(args) > 1 and os.path.isabs(cwd):
        artisan = os.path.realpath(Path(cwd) / args[1])
    hashed = digest(json.dumps(args).encode())
    direct = (len(args) >= 3 and re.fullmatch(r"/usr/bin/php(?:8\.4)?", args[0]) is not None
              and os.path.realpath(executable) == os.path.realpath(args[0]) == "/usr/bin/php8.4"
              and artisan == str(APP / "artisan") and args[2] == expected_command)
    return {"exact_direct_live_command": direct, "argv_sha256": hashed,
            "known_argv_hash_matches": hashed == EXPECTED_ARGV_HASHES.get(label),
            "live_app_cwd": os.path.realpath(cwd) == str(APP) if os.path.isabs(cwd) else False,
            "force": any(x == "--force" or x.startswith("--force=") for x in args)}


def unit_command(value, cwd, expected_command, label):
    require(value.count("path=") == value.count("argv[]=") == 1 and value.strip().endswith("}"), "UNIT_ARGV_UNVERIFIED")
    match = re.match(r"\s*\{\s*path=([^;]+?)\s*;\s*argv\[\]=(.*?) ;", value)
    require(match is not None and not any(c in match.group(2) for c in ("$", "\\")), "UNIT_ARGV_UNVERIFIED")
    return argv_evidence(shlex.split(match.group(2)), match.group(1), cwd, expected_command, label)


def properties(unit):
    names = property_names(unit)
    raw, _ = command(["/usr/bin/systemctl", "show", unit, "--all", "--property=" + ",".join(names)])
    lines = raw.decode().splitlines()
    values = {}
    for line in lines:
        key, sep, value = line.partition("=")
        require(sep and key not in values and key in names, "UNIT_PROPERTIES_UNVERIFIED")
        values[key] = value
    require(set(values) == set(names), "UNIT_PROPERTIES_INCOMPLETE")
    return values, digest(raw)


def cgroup_state(value):
    require(re.fullmatch(r"/(?:[A-Za-z0-9_.:@-]+/)*[A-Za-z0-9_.:@-]+", value) is not None
            and all(x not in (".", "..") for x in value.split("/")[1:]), "CGROUP_UNVERIFIED")
    path = Path("/sys/fs/cgroup") / value.lstrip("/")
    require(str(path) == os.path.realpath(path), "CGROUP_PATH_UNVERIFIED")
    members = [int(x) for x in read_file(path / "cgroup.procs", 65536).split()]
    events = dict(line.split() for line in read_file(path / "cgroup.events", 65536).decode().splitlines())
    require(set(events) <= {"populated", "frozen"} and all(v in {"0", "1"} for v in events.values()), "CGROUP_EVENTS_UNVERIFIED")
    return {"member_pids": members, "populated": events.get("populated", "UNVERIFIED"),
            "frozen": events.get("frozen", "UNVERIFIED"), "subtree_processes_verified": False}


def unit_inventory():
    account = pwd.getpwnam("kmjprod"); require(account.pw_uid > 0, "SERVICE_UID_UNSAFE")
    result = {}
    for index, unit in enumerate(UNITS):
        values, hashed = properties(unit)
        if unit == UNITS[2]:
            result[unit] = {"ActiveState": values["ActiveState"], "SubState": values["SubState"],
                            "properties_sha256": hashed, "exact_scheduler_trigger": values["Triggers"] == UNITS[1]}
            continue
        item = {key: values[key] for key in ("ActiveState", "SubState", "Type", "MainPID", "Restart", "KillMode", "TimeoutStopUSec")}
        item.update({"properties_sha256": hashed, "unit_user_is_kmjprod": values["User"] == "kmjprod",
                     "cgroup": section(lambda: cgroup_state(values["ControlGroup"]))})
        if index < 2:
            label, expected = (("queue", "queue:work"), ("scheduler", "schedule:run"))[index]
            item["unit_command"] = section(lambda: unit_command(values["ExecStart"], values["WorkingDirectory"], expected, label))
            pid = int(values["MainPID"])
            def runtime():
                before = process(pid)
                evidence = argv_evidence(before["args"], before["exe"], before["cwd"], expected, label)
                evidence.update({"all_uids_kmjprod": before["uids"] == [account.pw_uid] * 4,
                                 "host_network_namespace": before["netns"] == namespace(), "start_time": before["start"]})
                require(process(pid) == before, "PROCESS_CHANGED")
                return evidence
            item["runtime"] = section(runtime) if pid > 0 else {"observed": False, "reason": "NO_PROCESS"}
            item["queue_idle_attested"] = False
        result[unit] = item
    return result


def output_priority(document):
    """Inspect every OUTPUT family; choose typed signed-int max+1, no symbols."""
    require(type(document) is dict and set(document) == {"nftables"} and type(document["nftables"]) is list, "NFT_SCHEMA_UNVERIFIED")
    priorities, families = [], []
    for record in document["nftables"]:
        require(type(record) is dict and len(record) == 1, "NFT_RECORD_UNVERIFIED")
        if "chain" not in record:
            continue
        chain = record["chain"]; require(type(chain) is dict, "NFT_CHAIN_UNVERIFIED")
        if chain.get("hook") != "output":
            continue
        family, priority = chain.get("family"), chain.get("prio")
        require(family in {"ip", "ip6", "inet", "arp", "bridge", "netdev"}, "NFT_FAMILY_UNVERIFIED")
        require(type(priority) is int and -(2**31) <= priority < 2**31 - 1, "NFT_PRIORITY_UNVERIFIED")
        families.append(family); priorities.append(priority)
    return {"proposed_priority": max(priorities, default=-1) + 1, "output_families": sorted(set(families)),
            "cross_family_hook_semantics_verified": not bool(set(families) & {"arp", "bridge", "netdev"}),
            "ruleset_recheck_before_mutation_required": True}


def dependency_inventory():
    def inspect(path, name):
        hashed = digest(read_file(path, protected=True))
        return {"sha256": hashed, "pin_matches": hashed == PINS[name]}
    result = {name: section(lambda p=path, n=name: inspect(p, n)) for name, path in DEPENDENCIES.items()}
    def materializer():
        hashed = digest(read_file(MATERIALIZER_SOURCE))
        matches = hashed == PINS["materializer"]
        return {"sha256": hashed, "pin_matches": matches, "protected_root_install_verified": False,
                "installation": "SOURCE_PINNED_NOT_ROOT_INSTALLED" if matches else "SOURCE_PIN_MISMATCH"}
    result["materializer"] = section(materializer)
    return result


def lock_inventory():
    path = Path(RELEASE_LOCK)
    for parent in path.parents:
        st = parent.lstat()
        require(stat.S_ISDIR(st.st_mode) and st.st_uid == 0 and (not st.st_mode & 0o022 or st.st_mode & stat.S_ISVTX), "LOCK_PARENT_UNSAFE")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        info = os.fstat(fd); named = path.lstat()
        valid = stat.S_ISREG(info.st_mode) and info.st_uid == info.st_gid == 0 and info.st_nlink == 1 and stat.S_IMODE(info.st_mode) == 0o600
        require(valid and (info.st_dev, info.st_ino) == (named.st_dev, named.st_ino), "LOCK_UNSAFE")
        return {"protected_root_0600_single_link": True, "device": info.st_dev, "inode": info.st_ino,
                "lock_acquired": False, "availability_verified": False}
    finally:
        os.close(fd)


def maintenance_inventory():
    raw = read_file(APP / ".env", 65536).decode()
    values = []
    for line in raw.splitlines():
        if re.match(r"\s*APP_MAINTENANCE_DRIVER\s*=", line):
            match = re.fullmatch(r"\s*APP_MAINTENANCE_DRIVER\s*=\s*([\"']?)(file|cache)\1\s*", line)
            values.append(match.group(2) if match else "UNVERIFIED")
    declared = values[0] if len(values) == 1 else "UNVERIFIED"
    cached = os.path.lexists(APP / "bootstrap/cache/config.php")
    return {"driver_declaration": declared, "config_cache_present": cached,
            "uncached_explicit_file_driver": declared == "file" and not cached,
            "live_down_marker_present": os.path.lexists(APP / "storage/framework/down"),
            "shared_down_marker_present": os.path.lexists(Path(SHARED) / "framework/down"),
            "effective_application_config_executed": False}


def framework_inventory():
    worker = digest(read_file(APP / "vendor/laravel/framework/src/Illuminate/Queue/Worker.php"))
    locked = json.loads(read_file(APP / "composer.lock", 4 * 1048576))
    frameworks = [p for p in locked.get("packages", []) if p.get("name") == "laravel/framework"]
    return {"worker_sha256": worker, "official_worker_matches": worker == WORKER_HASH,
            "composer_reference_matches": len(frameworks) == 1 and frameworks[0].get("source", {}).get("reference") == FRAMEWORK_REF,
            "runtime_signal_handler_attested": False, "application_bootstrapped": False}


def pool_config(raw):
    selected, values, count = False, {}, 0
    allowed = {"user", "group", "listen", "pm", "pm.process_idle_timeout", "pm.status_path", "pm.status_listen", "env[LARAVEL_STORAGE_PATH]"}
    for line in raw.decode().splitlines():
        line = line.split("NOTICE:", 1)[-1].strip()
        match = re.fullmatch(r"\[([^]]+)\]", line)
        if match:
            selected = match.group(1) == POOL
            count += int(selected)
        elif selected and " = " in line:
            key, value = line.split(" = ", 1)
            if key in allowed:
                require(key not in values, "DUPLICATE_POOL_DIRECTIVE")
                values[key] = value
    require(count == 1, "POOL_MISSING_OR_AMBIGUOUS")
    return {"user_kmjprod": values.get("user") == "kmjprod", "ondemand": values.get("pm") == "ondemand",
            "listen_exact": values.get("listen") == "127.0.0.1:21084",
            "status_path_undefined": values.get("pm.status_path") == "undefined",
            "status_listener_undefined": values.get("pm.status_listen") == "undefined",
            "storage_override_declared": "env[LARAVEL_STORAGE_PATH]" in values,
            "storage_override_matches_live_storage": values.get("env[LARAVEL_STORAGE_PATH]") == str(APP / "storage"),
            "storage_override_matches_shared_storage": values.get("env[LARAVEL_STORAGE_PATH]") == SHARED,
            "idle_timeout_seconds": int(values["pm.process_idle_timeout"]) if re.fullmatch(r"\d+", values.get("pm.process_idle_timeout", "")) else "UNVERIFIED"}


def nginx_inventory():
    values, _ = properties("nginx.service")
    master = process(int(values["MainPID"])); require(master["uids"] == [0] * 4, "NGINX_MASTER_UNVERIFIED")
    require(master["exe"] == "/usr/sbin/nginx", "NGINX_MASTER_EXECUTABLE_UNVERIFIED")
    read_file("/usr/sbin/nginx", 64 * 1048576, protected=True)
    workers = []
    uid = pwd.getpwnam("www-data").pw_uid; require(uid > 0, "WEB_UID_UNSAFE")
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            item = process(int(entry.name))
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
        if item["ppid"] == master["pid"] and item["args"] and item["args"][0].startswith("nginx: worker process"):
            require(process(item["pid"]) == item, "NGINX_WORKER_CHANGED")
            workers.append({"pid": item["pid"], "all_uids_www_data": item["uids"] == [uid] * 4,
                            "host_netns": item["netns"] == namespace(), "same_executable_as_master": item["exe"] == master["exe"]})
    require(process(master["pid"]) == master, "NGINX_MASTER_CHANGED")
    return {"derived_www_data_uid": uid, "workers": workers, "workers_verified": bool(workers) and all(
        w["all_uids_www_data"] and w["host_netns"] and w["same_executable_as_master"] for w in workers)}


def owns_socket(pid, inode):
    for fd in (Path("/proc") / str(pid) / "fd").iterdir():
        try:
            if os.readlink(fd) == "socket:[" + inode + "]":
                return True
        except FileNotFoundError:
            continue
    return False


def production_listeners(text):
    found = []
    for line in text.splitlines()[1:]:
        fields = line.split()
        if fields[1] == "0100007F:525C" and fields[3] == "0A":
            found.append({"inode": fields[9], "backlog": int(fields[4].split(":")[1], 16)})
    return found


def fpm_process_inventory():
    values, _ = properties("php8.4-fpm.service")
    master = process(int(values["MainPID"]))
    uid = pwd.getpwnam("kmjprod").pw_uid; require(uid > 0, "SERVICE_UID_UNSAFE")
    listeners = production_listeners(Path("/proc/net/tcp").read_text())
    inode = listeners[0]["inode"] if len(listeners) == 1 else None
    workers = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            item = process(int(entry.name))
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
        if item["ppid"] == master["pid"] and item["args"] and item["args"][0] == "php-fpm: pool " + POOL:
            workers.append({"pid": item["pid"], "all_uids_kmjprod": item["uids"] == [uid] * 4,
                            "same_master_executable": item["exe"] == master["exe"],
                            "host_netns": item["netns"] == namespace(),
                            "holds_production_listener": bool(inode) and owns_socket(item["pid"], inode)})
            require(process(item["pid"]) == item, "FPM_WORKER_CHANGED")
    master_owns = bool(inode) and owns_socket(master["pid"], inode)
    require(process(master["pid"]) == master, "FPM_MASTER_CHANGED")
    return {"master_pid": master["pid"], "master_root_uids": master["uids"] == [0] * 4,
            "master_executable_exact": master["exe"] == "/usr/sbin/php-fpm8.4",
            "master_host_netns": master["netns"] == namespace(),
            "listeners": listeners, "single_listener_owned_by_master": len(listeners) == 1 and master_owns,
            "workers": workers, "workers_verified": bool(workers) and all(
                all(v for k, v in worker.items() if k != "pid") for worker in workers),
            "writer_quiescence_established": False}


def no_new_privileges():
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(38, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "NO_NEW_PRIVILEGES_FAILED")


def candidate_identity():
    account = pwd.getpwnam("kmjprod")
    require(os.path.realpath(CANDIDATE) == CANDIDATE, "CANDIDATE_PATH_UNVERIFIED")
    require(account.pw_uid > 0 and Path(CANDIDATE).stat().st_uid == account.pw_uid, "CANDIDATE_OWNER_UNVERIFIED")
    read_file("/usr/bin/git", 64 * 1048576, protected=True)
    def git(*args):
        result = subprocess.run(["/usr/bin/git", "--no-optional-locks", "-c", "safe.directory=" + CANDIDATE,
                                 "-c", "core.fsmonitor=false", "-C", CANDIDATE, *args],
                                user=account.pw_uid, group=account.pw_gid, extra_groups=[], preexec_fn=no_new_privileges,
                                env={**ENV, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
                                     "GIT_OPTIONAL_LOCKS": "0"}, stdin=subprocess.DEVNULL,
                                capture_output=True, check=True, timeout=15)
        require(len(result.stdout) <= 4096, "GIT_IDENTITY_TOO_LARGE")
        return result.stdout.decode().strip()
    require(git("rev-parse", "--show-toplevel") == CANDIDATE, "CANDIDATE_ROOT_UNVERIFIED")
    head = git("rev-parse", "--verify", "HEAD")
    require(re.fullmatch(r"[a-f0-9]{40}", head) is not None, "CANDIDATE_SHA_UNVERIFIED")
    return {"observed_sha": head, "expected_sha_matches": head == CANDIDATE_SHA,
            "source_cleanliness_attested": False, "git_uid": account.pw_uid}


def inventory():
    require(os.geteuid() == 0 and socket.gethostname().split(".")[0] == "KMJ-elite", "ROOT_ELITE_ONLY")
    require(str(Path("/home/kmjprod/current").resolve(strict=True)) == LIVE, "POINTER_CHANGED")
    require(namespace() == namespace(1), "HOST_NETNS_REQUIRED")
    def nft_inventory():
        raw, _ = command(["/usr/sbin/nft", "-j", "list", "ruleset"])
        return {"ruleset_sha256": digest(raw), **output_priority(json.loads(raw))}
    def fpm_inventory():
        out, err = command(["/usr/sbin/php-fpm8.4", "-tt"])
        return pool_config(out + b"\n" + err)
    def capabilities():
        value = int(next(x for x in Path("/proc/self/status").read_text().splitlines() if x.startswith("CapEff:")).split()[1], 16)
        return {"net_admin": bool(value & (1 << 12)), "sys_admin": bool(value & (1 << 21)), "linux_immutable": bool(value & (1 << 9))}
    def nginx_config():
        out, _ = command(["/usr/sbin/nginx", "-T"])
        return {"production_fastcgi_references": len(re.findall(rb"fastcgi_pass\s+127\.0\.0\.1:21084\s*;", out)),
                "config_dump_private": True}
    result = {"mutated": False, "ready_for_apply": False, "writer_quiescence_established": False,
              "candidate_sha_expected": CANDIDATE_SHA, "candidate_identity": section(candidate_identity),
              "candidate_path": CANDIDATE, "dependencies": dependency_inventory(),
              "release_lock": section(lock_inventory), "units": section(unit_inventory),
              "maintenance": section(maintenance_inventory), "framework": section(framework_inventory),
              "production_pool_config": section(fpm_inventory), "production_fpm_processes": section(fpm_process_inventory),
              "nginx_workers": section(nginx_inventory),
              "nginx_config": section(nginx_config),
              "nft": section(nft_inventory), "root_capabilities": section(capabilities),
              "unverified": ["effective_runtime_maintenance_driver", "queue_idle_after_maintenance_restart",
                             "effective_cli_storage_override", "materializer_protected_root_install",
                             "writer_quiescence", "native_apply_adapter"]}
    require(str(Path("/home/kmjprod/current").resolve(strict=True)) == LIVE, "POINTER_CHANGED")
    return result

# Print only fixed, sanitized values. The inventory() internal details include
# ephemeral PIDs/process state and are never emitted to chat/operator logs.
def status(section):
    if not isinstance(section, dict) or section.get("observed") is not True:
        return None
    return section.get("data") if isinstance(section.get("data"), dict) else None


def attest_report(inventory_doc: dict) -> dict[str, str]:
    def label(condition):
        return "YES" if condition is True else "NO_OR_UNVERIFIED"
    def section(name):
        return status(inventory_doc.get(name))
    def inner(obj, key):
        return status(obj.get(key)) if isinstance(obj, dict) else None

    units = section("units") or {}
    queue = units.get(UNITS[0], {})
    scheduler = units.get(UNITS[1], {})
    timer = units.get(UNITS[2], {})
    pool = section("production_pool_config") or {}
    fpm = section("production_fpm_processes") or {}
    nginx = section("nginx_workers") or {}
    nginx_cfg = section("nginx_config") or {}
    deps = section("dependencies") or {}
    nft = section("nft") or {}
    candidate = section("candidate_identity") or {}
    maintenance = section("maintenance") or {}
    capabilities = section("root_capabilities") or {}

    result = {
        "CURRENT_RELEASE": "platform-bce4100d005e",
        "CANDIDATE_SHA": CANDIDATE_SHA,
        "CANDIDATE_EXACT_GIT_HEAD": label(candidate.get("expected_sha_matches") is True),
        "LIVE_SHARED_CANDIDATE_ONLY_SWITCH": "REQUIRED",
        "LIVE_STORAGE_SWITCH_REQUIRED": "NO",
        "QUEUE_STATE": str(queue.get("ActiveState", "UNVERIFIED")).upper()
                       if queue.get("ActiveState") in {"active", "inactive", "activating", "deactivating", "failed"}
                       else "UNVERIFIED",
        "QUEUE_DIRECT_LIVE_COMMAND": label((inner(queue, "unit_command") or {}).get("exact_direct_live_command") is True),
        "QUEUE_OLD_ARGV_PINS_REUSED": "NO",
        "QUEUE_RESTART_ALWAYS": label(queue.get("Restart") == "always"),
        "QUEUE_RUNTIME_SCOPED": label((inner(queue, "runtime") or {}).get("all_uids_kmjprod") is True
                                      and (inner(queue, "runtime") or {}).get("host_network_namespace") is True),
        "SCHEDULER_STATE": str(scheduler.get("ActiveState", "UNVERIFIED")).upper()
                           if scheduler.get("ActiveState") in {"active", "inactive", "activating", "deactivating", "failed"}
                           else "UNVERIFIED",
        "SCHEDULER_DIRECT_LIVE_COMMAND": label((inner(scheduler, "unit_command") or {}).get("exact_direct_live_command") is True),
        "TIMER_EXACT_TRIGGER": label(timer.get("exact_scheduler_trigger") is True),
        "FPM_POOL_EXACT_LISTEN": label(pool.get("listen_exact") is True),
        "FPM_POOL_OWNER": label(pool.get("user_kmjprod") is True),
        "FPM_POOL_ONDEMAND": label(pool.get("ondemand") is True),
        "FPM_MASTER_LISTENER_IDENTITY": label(fpm.get("single_listener_owned_by_master") is True),
        "FPM_MASTER_SCOPE": label(fpm.get("master_root_uids") is True and
                                 fpm.get("master_executable_exact") is True and fpm.get("master_host_netns") is True),
        "NGINX_WORKERS_SCOPED": label(nginx.get("workers_verified") is True),
        "NGINX_FPM_UPSTREAM_PRESENT": label(type(nginx_cfg.get("production_fastcgi_references")) is int
                                             and nginx_cfg["production_fastcgi_references"] > 0),
        "MAINTENANCE_FILE_DRIVER_DECLARED": label(maintenance.get("uncached_explicit_file_driver") is True),
        "PINNED_SCANNER": label((inner(deps, "scanner") or {}).get("pin_matches") is True),
        "PINNED_SNAPSHOT_HELPER": label((inner(deps, "helper") or {}).get("pin_matches") is True),
        "MATERIALIZER_SOURCE_PINNED": label((inner(deps, "materializer") or {}).get("pin_matches") is True),
        "ROOT_CAP_NET_ADMIN": label(capabilities.get("net_admin") is True),
        "ROOT_CAP_LINUX_IMMUTABLE": label(capabilities.get("linux_immutable") is True),
        "NFT_IPV4_OUTPUT_REVIEW": label(nft.get("cross_family_hook_semantics_verified") is True),
        "ROOT_LOCK_SAFE": label((section("release_lock") or {}).get("protected_root_0600_single_link") is True),
        "WRITER_ADMISSION_CLOSED": "NOT_ATTESTED",
        "PROCESS_DRAIN_ATTESTED": "NO",
        "STORAGE_APPLY_ALLOWED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }
    return result


def main():
    print("SCHEMA=kmj.09e8.native-writer-inventory.readonly.v1", flush=True)
    try:
        report = attest_report(inventory())
        for key, value in report.items():
            print(f"{key}={value}")
        print("NATIVE_WRITER_INVENTORY=READ_ONLY_COMPLETE")
        return 0
    except (Blocked, OSError, ValueError, TypeError, KeyError,
            subprocess.SubprocessError) as exc:
        print("NATIVE_WRITER_INVENTORY=BLOCKED_UNVERIFIED")
        print("WRITER_ADMISSION_CLOSED=NOT_ATTESTED")
        print("PROCESS_DRAIN_ATTESTED=NO")
        print("STORAGE_APPLY_ALLOWED=NO")
        print("PRODUCTION_MUTATION=NONE")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
