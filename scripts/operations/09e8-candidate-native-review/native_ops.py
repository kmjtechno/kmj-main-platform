"""09e8 candidate-only native writer adapter. SOURCE REVIEW ONLY, no host CLI.

Only Transaction may order these operations. This adapter never flushes a
firewall, signals FPM workers, stops the shared master, or force-kills a job.
Unimplemented proof or unavailable runtime evidence raises Blocked.
"""
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import select
import socket
import stat
import subprocess
import time
import types

import native_plan as p
from orchestrator import (LIVE, CANDIDATE, CANDIDATE_SHA, SHARED, PINS, UNITS,
                          PREFLIGHT, DRAIN, SWITCHED, Blocked, require, canonical_json,
                          no_duplicates)

APP = Path(LIVE) / "apps/platform"  # CURRENT runtime writers, not scanner target
TARGET_APP = Path(CANDIDATE) / "apps/platform"  # ONLY permitted V6 storage target
STATE = "/var/lib/kmj-main-platform-09e8-candidate-cutover"
SCANNER_STATE = "/var/lib/kmj-main-platform-storage-switch"
QUEUE, SCHEDULER, TIMER = UNITS
PHP = "/usr/bin/php8.4"
PORT = 21084
POOL = "kmj-elite-stage"
MAX_DRAIN = 300
LIVE_SHA = "bce4100d005e8624509cab989c096d7eaab1ba79"
# Linux UAPI values; some Python builds omit these symbolic exports.
F_ADD_SEALS = getattr(fcntl, "F_ADD_SEALS", 1033)
ALL_SEALS = 0x01 | 0x02 | 0x04 | 0x08
TOOL_ENV = p.ENV

# Fixed code is evaluated only as the service account with its captured queue
# environment. Application bootstrap may have application side effects as that
# account; this is an explicitly invoked runtime probe, never a root import.
MAINTENANCE_PROBE = r'''
require getcwd().'/vendor/autoload.php';
$app=require getcwd().'/bootstrap/app.php';
$kernel=$app->make(Illuminate\Contracts\Console\Kernel::class); $kernel->bootstrap();
$mode=$app->maintenanceMode(); $worker=$app->make('queue.worker');
echo json_encode(['driver'=>config('app.maintenance.driver'),
 'class'=>get_class($mode),'worker'=>get_class($worker),
 'storage'=>$app->storagePath(),'active'=>$mode->active(),
 'config_cached'=>$app->configurationIsCached(),
 'cache_store'=>get_class($app->make('cache')->store()->getStore())],JSON_THROW_ON_ERROR);
'''


def write_all(fd, raw):
    while raw:
        count = os.write(fd, raw)
        require(count > 0, "SHORT_CONTROL_WRITE")
        raw = raw[count:]


def stamp(st):
    return [st.st_dev, st.st_ino]


def parse_environment(raw):
    require(raw.endswith(b"\0") and len(raw) <= 1048576, "QUEUE_ENVIRONMENT_INVALID")
    result = {}
    for item in raw[:-1].split(b"\0"):
        key, sep, value = item.partition(b"=")
        require(sep and re.fullmatch(rb"[A-Za-z_][A-Za-z0-9_]*", key) is not None, "QUEUE_ENVIRONMENT_INVALID")
        key, value = os.fsdecode(key), os.fsdecode(value)
        require(key not in result, "QUEUE_ENVIRONMENT_DUPLICATE")
        result[key] = value
    return result


def application_environment(env):
    """Only systemd invocation metadata may differ across worker generations."""
    formats = {"INVOCATION_ID": r"[a-f0-9]{32}", "JOURNAL_STREAM": r"[0-9]+:[0-9]+", "SYSTEMD_EXEC_PID": r"[1-9][0-9]*"}
    for key, pattern in formats.items():
        require(key not in env or re.fullmatch(pattern, env[key]) is not None, "SYSTEMD_ENV_METADATA_INVALID")
    return {key: value for key, value in env.items() if key not in formats}


def descendants(processes, parent):
    found = set()
    while True:
        new = {pid for pid, item in processes.items() if item["ppid"] in ({parent} | found)} - found
        if not new:
            return {pid: processes[pid] for pid in found}
        found |= new


def cgroup_members(path):
    require(path.startswith("/") and ".." not in path.split("/"), "CGROUP_PATH_INVALID")
    root = Path("/sys/fs/cgroup") / path.lstrip("/")
    require(str(root) == os.path.realpath(root), "CGROUP_PATH_REPLACED")
    result = set()
    for file in [root / "cgroup.procs", *root.glob("**/*/cgroup.procs")]:
        require(str(file) == os.path.realpath(file), "CGROUP_DESCENDANT_PATH_REPLACED")
        result.update(int(pid) for pid in p.read_file(file, 65536).split())
    return result


def bound_process(pid):
    before = p.process(pid)
    fd = os.pidfd_open(pid, 0)
    try:
        require(p.process(pid) == before and not select.select([fd], [], [], 0)[0], "PROCESS_REPLACED")
        return before, fd
    except BaseException:
        os.close(fd)
        raise


def exited(fd):
    return bool(select.select([fd], [], [], 0)[0])


def all_processes():
    result = {}
    for entry in Path("/proc").iterdir():
        if entry.name.isdigit():
            try:
                result[int(entry.name)] = p.process(int(entry.name))
            except (FileNotFoundError, ProcessLookupError):
                continue
    return result


def cgroup_empty(path):
    require(path.startswith("/") and ".." not in path.split("/"), "CGROUP_PATH_INVALID")
    root = Path("/sys/fs/cgroup") / path.lstrip("/")
    require(str(root) == os.path.realpath(root), "CGROUP_PATH_REPLACED")
    # cgroup.events populated includes descendants, unlike cgroup.procs alone.
    events = dict(line.split() for line in p.read_file(root / "cgroup.events", 65536).decode().splitlines())
    members = p.read_file(root / "cgroup.procs", 65536).split()
    require(events.get("populated") in ("0", "1"), "CGROUP_EVENTS_UNVERIFIED")
    return events["populated"] == "0" and not members


def ruleset_identity(raw):
    value = json.loads(raw, object_pairs_hook=no_duplicates)
    def visit(item):
        if type(item) is dict:
            for key, child in item.items():
                if key == "counter" and type(child) is dict:
                    for metric in ("packets", "bytes"):
                        if metric in child:
                            require(type(child[metric]) is int and child[metric] >= 0, "NFT_COUNTER_UNTYPED")
                            child[metric] = 0
                visit(child)
        elif type(item) is list:
            for child in item:
                visit(child)
    visit(value)
    return p.digest(canonical_json(value))


class NativeOps:
    def __init__(self, store, release_lock):
        self.store = store
        self.release_lock = release_lock
        state_info = os.fstat(store.fd)
        require(stat.S_ISDIR(state_info.st_mode) and state_info.st_uid == 0
                and stat.S_IMODE(state_info.st_mode) == 0o700, "NATIVE_STATE_DIRECTORY_MUST_BE_ROOT_0700")
        self.account = pwd.getpwnam("kmjprod")
        require(self.account.pw_uid > 0, "SERVICE_UID_UNSAFE")
        self.evidence = {}
        self.env = None
        self.marker_dir = None
        self.queue_fd = None
        self.fpm_fds = {}
        self.queue_child_fds = {}
        self.flags = {}
        self.modules = {}

    def close(self):
        for fd in [self.marker_dir, self.queue_fd, *self.fpm_fds.values(), *self.queue_child_fds.values()]:
            if fd is not None:
                os.close(fd)
        self.marker_dir = self.queue_fd = None
        self.fpm_fds = {}
        self.queue_child_fds = {}

    def checkpoint(self):
        state = self.store.read()
        require(state is not None and state.get("recovery_evidence", {}).get("nonce") == self.evidence["nonce"],
                "TRANSACTION_BINDING_CHANGED")
        state["recovery_evidence"] = self.evidence
        self.store.write(state)

    def pointer(self):
        require(str(Path("/home/kmjprod/current").resolve(strict=True)) == LIVE, "POINTER_CHANGED")
        require(p.namespace() == self.evidence.get("netns", p.namespace(1)) == p.namespace(1), "NETNS_CHANGED")
        live_storage = APP / "storage"
        require(live_storage.is_symlink() and os.readlink(live_storage) == SHARED,
                "LIVE_STORAGE_LINK_CHANGED")
        shared_inode = stamp(Path(SHARED).stat())[:2]
        require(stamp(live_storage.stat())[:2] == shared_inode, "LIVE_SHARED_INODE_CHANGED")
        if "live_shared_inode" in self.evidence:
            require(tuple(self.evidence["live_shared_inode"]) == tuple(shared_inode),
                    "LIVE_SHARED_IDENTITY_CHANGED")

    def execute(self, args, *, service=False, data=None, timeout=25):
        require(type(args) is list and args and args[0] in {
            "/usr/sbin/nft", "/usr/bin/systemctl", PHP, "/usr/bin/python3", "/usr/bin/bash"}, "COMMAND_NOT_FIXED_TOOL")
        p.read_file(str(Path(args[0]).resolve(strict=True)), 64 * 1048576, protected=True)
        kwargs = {}
        if service:
            require(self.env is not None, "QUEUE_CONTEXT_NOT_CAPTURED")
            kwargs.update(user=self.account.pw_uid, group=self.account.pw_gid, extra_groups=[], preexec_fn=p.no_new_privileges)
        result = subprocess.run(args, input=data, stdin=None if data is not None else subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=True,
                                env=self.env if service else TOOL_ENV, cwd=APP if service else "/", **kwargs)
        require(len(result.stdout) + len(result.stderr) <= 8 * 1048576, "COMMAND_OUTPUT_TOO_LARGE")
        return result.stdout

    def systemctl(self, operation, unit):
        require(operation in {"start", "stop"} and unit in UNITS, "UNIT_MUTATION_OUT_OF_SCOPE")
        # Stop is asynchronous; bounded polling observes natural completion.
        return self.execute(["/usr/bin/systemctl", operation, "--no-block", unit])

    def module(self, name):
        if name not in self.modules:
            raw = p.read_file(p.DEPENDENCIES[name], protected=True)
            require(p.digest(raw) == PINS[name], "DEPENDENCY_PIN_MISMATCH")
            module = types.ModuleType("verified_cutover_" + name)
            module.__file__ = p.DEPENDENCIES[name]
            exec(compile(raw, module.__file__, "exec"), module.__dict__)
            self.modules[name] = module
        return self.modules[name]

    def wait(self, predicate, seconds=MAX_DRAIN):
        require(type(seconds) in (int, float) and 0 < seconds <= MAX_DRAIN, "DEADLINE_INVALID")
        deadline = time.monotonic() + seconds
        while True:
            self.pointer()
            if predicate():
                return
            require(time.monotonic() < deadline, "DRAIN_DEADLINE_EXPIRED")
            time.sleep(0.2)

    def private_environment(self):
        before = p.process(self.evidence["queue_original"]["pid"])
        require(before == self.evidence["queue_original"], "QUEUE_CHANGED_BEFORE_ENV_CAPTURE")
        raw = p.read_file(f"/proc/{before['pid']}/environ")
        self.env = parse_environment(raw)
        require(p.process(before["pid"]) == before, "QUEUE_CHANGED_DURING_ENV_CAPTURE")
        self.persist_environment()

    def persist_environment(self, replacement=False):
        name = "queue-environment-" + self.evidence["nonce"] + ("-replacement" if replacement else "") + ".json"
        data = canonical_json(self.env)
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                     0o600, dir_fd=self.store.fd)
        try:
            write_all(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.fsync(self.store.fd)
        self.evidence["environment"] = {"name": name, "sha256": p.digest(data)}
        self.checkpoint()

    def maintenance_probe(self, active):
        self.pointer()
        value = json.loads(self.execute([PHP, "-r", MAINTENANCE_PROBE], service=True), object_pairs_hook=no_duplicates)
        require(set(value) == {"driver", "class", "worker", "storage", "active", "config_cached", "cache_store"}, "MAINTENANCE_PROBE_SCHEMA")
        require(value["driver"] == "file" and value["class"] == "Illuminate\\Foundation\\FileBasedMaintenanceMode"
                and value["worker"] == "Illuminate\\Queue\\Worker" and value["config_cached"] is False
                and value["storage"] in (str(APP / "storage"), SHARED) and value["active"] is active,
                "EFFECTIVE_MAINTENANCE_UNVERIFIED")
        require("maintenance_storage" not in self.evidence or value["storage"] == self.evidence["maintenance_storage"],
                "MAINTENANCE_STORAGE_CONTEXT_CHANGED")
        require(value["cache_store"] in {"Illuminate\\Cache\\" + name for name in
                ("FileStore", "RedisStore", "DatabaseStore", "MemcachedStore", "DynamoDbStore")}, "RESTART_CACHE_NOT_CROSS_PROCESS")
        require(p.framework_inventory()["official_worker_matches"], "WORKER_SOURCE_CHANGED")
        return value

    def preflight(self):
        require(os.geteuid() == 0 and socket.gethostname().split(".")[0] == "KMJ-elite", "ROOT_ELITE_ONLY")
        self.pointer()
        helper = self.module("helper")
        self.module("scanner")
        require(helper.git_identity(Path(CANDIDATE), CANDIDATE_SHA) is None, "CANDIDATE_IDENTITY_UNVERIFIED")
        candidate_app = TARGET_APP
        require(candidate_app.is_dir() and not candidate_app.is_symlink(), "CANDIDATE_APP_UNTRUSTED")
        require(stat.S_ISDIR((candidate_app / "storage").lstat().st_mode)
                and not (candidate_app / "storage").is_symlink(), "CANDIDATE_STORAGE_NOT_PHYSICAL")
        require(not os.path.lexists(candidate_app / ".env"), "CANDIDATE_ALREADY_MATERIALIZED")
        require(p.digest(p.read_file(p.MATERIALIZER_SOURCE, protected=True))
                == PINS["materializer"], "ROOT_MATERIALIZER_PIN_MISMATCH")
        require(not os.path.lexists(candidate_app / "storage/framework/down"),
                "CANDIDATE_MAINTENANCE_UNEXPECTED")
        require((APP / "storage").is_symlink() and os.readlink(APP / "storage") == SHARED,
                "LIVE_STORAGE_NOT_SHARED")
        # git_identity returns no value on successful verification.
        live_sha = helper.git_read(Path(LIVE), "rev-parse", "--verify", "HEAD").strip()
        require(live_sha == LIVE_SHA, "LIVE_GIT_IDENTITY_UNVERIFIED")
        helper.git_identity(Path(LIVE), live_sha)
        require(p.maintenance_inventory()["uncached_explicit_file_driver"], "FILE_MAINTENANCE_NOT_DECLARED")
        require(not os.path.lexists(APP / "storage/framework/down")
                and not os.path.lexists(Path(SHARED) / "framework/down"), "PREEXISTING_MAINTENANCE")
        require(p.framework_inventory()["official_worker_matches"], "WORKER_SOURCE_UNVERIFIED")
        unit_values, original = {}, {}
        for unit in UNITS:
            values, hashed = p.properties(unit)
            require(values["ActiveState"] in ("active", "inactive"), "UNIT_TRANSITIONING")
            original[unit] = values["ActiveState"]
            unit_values[unit] = values
        require(original == {QUEUE: "active", SCHEDULER: "inactive", TIMER: "active"}, "UNEXPECTED_ORIGINAL_UNITS")
        for label, unit, cmd in (("queue", QUEUE, "queue:work"), ("scheduler", SCHEDULER, "schedule:run")):
            values = unit_values[unit]
            scope = p.unit_command(values["ExecStart"], values["WorkingDirectory"], cmd, label)
            require(scope["exact_direct_live_command"] and scope["known_argv_hash_matches"]
                    and scope["live_app_cwd"] and not scope["force"] and values["User"] == "kmjprod", "UNIT_SCOPE_UNVERIFIED")
        # queue:restart ends the old worker with exit 0; only Restart=always brings
        # the maintenance-idle replacement that the drain step waits for. Refuse
        # before any mutation instead of timing out behind the admission guard.
        require(unit_values[QUEUE]["Restart"] == "always", "QUEUE_RESTART_POLICY_CANNOT_REPLACE_WORKER")
        require(unit_values[SCHEDULER]["Type"] == "oneshot" and unit_values[SCHEDULER]["Restart"] == "no"
                and unit_values[TIMER]["Triggers"] == SCHEDULER, "SCHEDULER_SCOPE_UNVERIFIED")
        queue, self.queue_fd = bound_process(int(unit_values[QUEUE]["MainPID"]))
        self.verify_queue(queue)
        fpm = p.fpm_process_inventory()
        require(fpm["master_root_uids"] and fpm["master_executable_exact"] and fpm["master_host_netns"]
                and fpm["single_listener_owned_by_master"], "FPM_SCOPE_UNVERIFIED")
        out, err = p.command(["/usr/sbin/php-fpm8.4", "-tt"])
        pool = p.pool_config(out + b"\n" + err)
        require(all(pool[key] for key in ("user_kmjprod", "ondemand", "listen_exact", "status_path_undefined", "status_listener_undefined"))
                and type(pool["idle_timeout_seconds"]) is int and 1 <= pool["idle_timeout_seconds"] <= 60,
                "FPM_POOL_CONFIG_UNVERIFIED")
        nginx = p.nginx_inventory()
        require(nginx["workers_verified"], "NGINX_IDENTITY_UNVERIFIED")
        raw, _ = p.command(["/usr/sbin/nft", "-j", "list", "ruleset"])
        priorities = p.output_priority(json.loads(raw, object_pairs_hook=no_duplicates))
        require(priorities["cross_family_hook_semantics_verified"], "NFT_OUTPUT_SCOPE_UNVERIFIED")
        self.evidence = {"nonce": os.urandom(16).hex(), "netns": p.namespace(), "live_sha": live_sha,
                         "queue_original": queue, "original_units": unit_values,
                         "fpm_master": p.process(fpm["master_pid"]), "listener_inode": fpm["listeners"][0]["inode"],
                         "pool": pool, "nginx_uid": nginx["derived_www_data_uid"],
                         "ruleset_sha256": ruleset_identity(raw), "guard_priority": priorities["proposed_priority"],
                         "marker": None, "maintenance_initially_absent": True, "queue_descendants": []}
        storage = TARGET_APP / "storage"
        require(stat.S_ISDIR(storage.lstat().st_mode) and not storage.is_symlink(),
                "CANDIDATE_STORAGE_NOT_PHYSICAL")
        self.evidence["original_storage"] = stamp(storage.stat())
        self.evidence["live_shared_inode"] = list(stamp(Path(SHARED).stat())[:2])
        # Unknown same-account processes are a real admission hole, not a PASS.
        self.verify_writer_inventory()
        self.env = parse_environment(p.read_file(f"/proc/{queue['pid']}/environ"))
        application_environment(self.env)
        require(p.process(queue["pid"]) == queue, "QUEUE_CHANGED_DURING_PREFLIGHT")
        maintenance = self.maintenance_probe(False)
        self.evidence["maintenance_storage"] = maintenance["storage"]
        # This proves the current CLI context's cross-process cache class, not
        # the old worker's cache visibility. Its actual exit is required later.
        observed = dict.fromkeys(PREFLIGHT, True)
        return observed, original

    def verify_queue(self, item):
        evidence = p.argv_evidence(item["args"], item["exe"], item["cwd"], "queue:work", "queue")
        require(item["uids"] == [self.account.pw_uid] * 4 and item["netns"] == p.namespace()
                and evidence["exact_direct_live_command"] and evidence["known_argv_hash_matches"]
                and evidence["live_app_cwd"] and not evidence["force"], "QUEUE_RUNTIME_SCOPE_UNVERIFIED")

    def verify_writer_inventory(self):
        processes = all_processes()
        queue_pid = self.evidence["queue_original"]["pid"]
        children = descendants(processes, queue_pid)
        require(all(item["uids"] == [self.account.pw_uid] * 4 and item["netns"] == self.evidence["netns"]
                    for item in children.values()), "QUEUE_DESCENDANT_SCOPE_UNVERIFIED")
        self.evidence["queue_descendants"] = list(children.values())
        allowed = {queue_pid, *children}
        master = self.evidence["fpm_master"]
        for pid, item in processes.items():
            if self.account.pw_uid not in item["uids"]:
                continue
            target = (item["ppid"] == master["pid"] and item["exe"] == master["exe"]
                      and item["args"] == ["php-fpm: pool " + POOL]
                      and item["uids"] == [self.account.pw_uid] * 4 and item["netns"] == self.evidence["netns"])
            require(pid in allowed or target, "UNACCOUNTED_SERVICE_ACCOUNT_PROCESS")

    def recovery_evidence(self):
        return self.evidence

    def guard_identity(self):
        return {"family": "inet", "table": "kmj_storage_" + self.evidence["nonce"], "chain": "out",
                "comment": "kmj-storage-" + self.evidence["nonce"], "priority": self.evidence["guard_priority"],
                "netns": self.evidence["netns"], "destination": "127.0.0.1", "port": PORT}

    def guard_script(self):
        guard = self.guard_identity()
        return (f"add table inet {guard['table']}\n"
                f"add chain inet {guard['table']} out {{ type filter hook output priority {guard['priority']}; policy accept; }}\n"
                f"add rule inet {guard['table']} out ip daddr 127.0.0.1 tcp dport {PORT} tcp flags & syn == syn counter reject with tcp reset comment \"{guard['comment']}\"\n").encode()

    def guard_counter(self):
        self.pointer()
        guard = self.guard_identity()
        raw = self.execute(["/usr/sbin/nft", "-j", "list", "table", "inet", guard["table"]])
        doc = json.loads(raw, object_pairs_hook=no_duplicates)
        chains = [record["chain"] for record in doc["nftables"] if "chain" in record]
        rules = [record["rule"] for record in doc["nftables"] if "rule" in record]
        require(len(chains) == len(rules) == 1, "GUARD_CONTENT_CHANGED")
        chain, rule = chains[0], rules[0]
        require(chain.get("family") == "inet" and chain.get("table") == guard["table"] and chain.get("name") == "out"
                and chain.get("type") == "filter" and chain.get("hook") == "output"
                and chain.get("prio") == guard["priority"] and chain.get("policy") == "accept", "GUARD_CHAIN_CHANGED")
        require(rule.get("family") == "inet" and rule.get("table") == guard["table"] and rule.get("chain") == "out"
                and rule.get("comment") == guard["comment"], "GUARD_RULE_CHANGED")
        expressions = rule.get("expr", [])
        expected_matches = [
            {"match": {"op": "==", "left": {"payload": {"protocol": "ip", "field": "daddr"}}, "right": "127.0.0.1"}},
            {"match": {"op": "==", "left": {"payload": {"protocol": "tcp", "field": "dport"}}, "right": PORT}},
            {"match": {"op": "==", "left": {"&": [{"payload": {"protocol": "tcp", "field": "flags"}}, "syn"]}, "right": "syn"}},
        ]
        require(len(expressions) == 5 and expressions[:3] == expected_matches
                and set(expressions[3]) == {"counter"} and expressions[4] == {"reject": {"type": "tcp reset"}}, "GUARD_EXPRESSION_CHANGED")
        value = expressions[3]["counter"].get("packets")
        require(type(value) is int and value >= 0, "GUARD_COUNTER_UNVERIFIED")
        return value

    def install_guard(self):
        self.pointer()
        # Recovery needs the original queue context even if the process dies
        # before the maintenance marker is created.
        self.private_environment()
        raw, _ = p.command(["/usr/sbin/nft", "-j", "list", "ruleset"])
        require(ruleset_identity(raw) == self.evidence["ruleset_sha256"], "NFT_BASELINE_CHANGED")
        self.execute(["/usr/sbin/nft", "-f", "-"], data=self.guard_script())
        self.evidence["guard_installed"] = True
        self.checkpoint()
        before = self.guard_counter()
        nginx = p.nginx_inventory()
        require(nginx["workers_verified"] and nginx["derived_www_data_uid"] == self.evidence["nginx_uid"], "NGINX_IDENTITY_CHANGED")
        # Connect only, no FastCGI bytes. If guard fails, abort before storage.
        script = "import socket,sys; s=socket.socket(); s.settimeout(2); r=s.connect_ex(('127.0.0.1',21084)); s.close(); sys.exit(0 if r==111 else 2)"
        account = pwd.getpwuid(self.evidence["nginx_uid"])
        p.read_file(str(Path("/usr/bin/python3").resolve(strict=True)), 64 * 1048576, protected=True)
        subprocess.run(["/usr/bin/python3", "-I", "-B", "-c", script], user=account.pw_uid,
                       group=account.pw_gid, extra_groups=[], preexec_fn=p.no_new_privileges,
                       env=TOOL_ENV, stdin=subprocess.DEVNULL, capture_output=True, timeout=5, check=True)
        self.wait(lambda: self.guard_counter() > before, 3)
        self.flags["nginx_uid_syn_counter_advanced"] = True

    def pause_timer(self):
        self.guard_counter()
        self.systemctl("stop", TIMER)
        self.wait(lambda: p.properties(TIMER)[0]["ActiveState"] == "inactive", 15)

    def drain_scheduler(self):
        original = self.evidence["original_units"][SCHEDULER]
        def done():
            values, _ = p.properties(SCHEDULER)
            require(values["ExecStart"] == original["ExecStart"], "SCHEDULER_COMMAND_CHANGED")
            return self.unit_empty(SCHEDULER, values)
        self.wait(done)
        self.flags["scheduler_cgroup_empty"] = True

    def unit_empty(self, unit, values=None):
        require(unit in (QUEUE, SCHEDULER), "CGROUP_UNIT_SCOPE_INVALID")
        values = values or p.properties(unit)[0]
        if values["ActiveState"] != "inactive" or values["MainPID"] != "0":
            return False
        path = values["ControlGroup"] or self.evidence["original_units"][unit]["ControlGroup"]
        if not path:
            raw = self.execute(["/usr/bin/systemctl", "show", unit, "--property=Slice"])
            require(raw == b"Slice=system.slice\n", "INACTIVE_UNIT_SLICE_UNVERIFIED")
            path = "/system.slice/" + unit
        try:
            return cgroup_empty(path)
        except FileNotFoundError:
            return True  # only explicit inactive+MainPID0 permits absence

    def open_marker_directory(self):
        storage = self.evidence["maintenance_storage"]
        require(storage in (str(APP / "storage"), SHARED), "STORAGE_PATH_UNEXPECTED")
        directory = Path(storage) / "framework"
        require(os.path.realpath(storage) in (str(APP / "storage"), SHARED), "STORAGE_PATH_UNEXPECTED")
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        st = os.fstat(fd)
        require(st.st_uid == self.account.pw_uid and stamp(st) == stamp(directory.stat()), "FRAMEWORK_DIRECTORY_UNVERIFIED")
        if "marker_directory" in self.evidence:
            require(self.evidence["marker_directory"] == stamp(st), "FRAMEWORK_DIRECTORY_CHANGED")
        else:
            self.evidence["marker_directory"] = stamp(st)
        self.marker_dir = fd

    def marker_payload(self):
        return canonical_json({"time": self.evidence.get("maintenance_time", 0), "message": "Service Unavailable",
                               "retry": 60, "refresh": None, "status": 503, "template": None,
                               "redirect": None, "except": [], "kmj_storage_nonce": self.evidence["nonce"]})

    def marker_bound(self):
        require(self.marker_dir is not None and stamp(os.fstat(self.marker_dir)) == self.evidence["marker_directory"]
                == stamp((Path(self.evidence["maintenance_storage"]) / "framework").stat()), "FRAMEWORK_DIRECTORY_CHANGED")
        fd = os.open("down", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=self.marker_dir)
        try:
            info = os.fstat(fd)
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == self.account.pw_uid
                    and stamp(info) == self.evidence["marker"] and info.st_size <= 4096
                    and os.read(fd, 4097) == self.marker_payload(), "MAINTENANCE_MARKER_CHANGED")
        finally:
            os.close(fd)

    def maintenance_on(self):
        self.guard_counter()
        self.maintenance_probe(False)
        self.open_marker_directory()
        self.evidence["maintenance_time"] = int(time.time())
        self.checkpoint()
        fd = os.open("down", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                     0o600, dir_fd=self.marker_dir)
        try:
            write_all(fd, self.marker_payload())
            os.fchown(fd, self.account.pw_uid, self.account.pw_gid)
            os.fchmod(fd, 0o600)
            os.fsync(fd)
            self.evidence["marker"] = stamp(os.fstat(fd))
            self.checkpoint()
        finally:
            os.close(fd)
        os.fsync(self.marker_dir)
        self.marker_bound()
        self.maintenance_probe(True)

    def queue_restart(self):
        self.marker_bound()
        self.maintenance_probe(True)
        require(p.process(self.evidence["queue_original"]["pid"]) == self.evidence["queue_original"], "QUEUE_GENERATION_CHANGED")
        self.track_queue_descendants()
        self.execute([PHP, str(APP / "artisan"), "queue:restart", "--no-interaction"], service=True)
        self.evidence["restart_requested"] = True
        self.checkpoint()

    def drain_and_stop_queue(self):
        def old_generation_drained():
            if not exited(self.queue_fd):
                self.track_queue_descendants()
            return exited(self.queue_fd) and all(exited(fd) for fd in self.queue_child_fds.values())
        self.wait(old_generation_drained)
        def replacement():
            values, _ = p.properties(QUEUE)
            pid = int(values["MainPID"])
            if not pid:
                return False
            item = p.process(pid)
            require((item["pid"], item["start"]) != (self.evidence["queue_original"]["pid"], self.evidence["queue_original"]["start"]), "OLD_QUEUE_GENERATION")
            self.verify_queue(item)
            replacement_env = parse_environment(p.read_file(f"/proc/{pid}/environ"))
            require(application_environment(replacement_env) == application_environment(self.env), "QUEUE_ENVIRONMENT_CHANGED")
            self.env = replacement_env
            self.marker_bound()
            self.maintenance_probe(True)
            require(not any(child["ppid"] == pid for child in all_processes().values()), "QUEUE_CHILD_PROCESS_PRESENT")
            self.evidence["queue_replacement"] = item
            self.persist_environment(replacement=True)
            self.checkpoint()
            return True
        self.wait(replacement, 30)
        self.install_queue_stop_override()
        self.marker_bound()
        self.maintenance_probe(True)
        self.systemctl("stop", QUEUE)
        cg = self.evidence["original_units"][QUEUE]["ControlGroup"]
        self.wait(lambda: self.unit_empty(QUEUE), 30)
        self.remove_queue_stop_override()
        self.flags.update(old_queue_generation_exited=True, replacement_queue_maintenance_idle=True, queue_cgroup_empty=True)

    def track_queue_descendants(self):
        processes = all_processes()
        current = descendants(processes, self.evidence["queue_original"]["pid"])
        known = {(item["pid"], item["start"]): item for item in self.evidence["queue_descendants"]}
        changed = False
        for item in [*known.values(), *current.values()]:
            require(item["uids"] == [self.account.pw_uid] * 4 and item["netns"] == self.evidence["netns"], "QUEUE_DESCENDANT_SCOPE_UNVERIFIED")
            key = (item["pid"], item["start"])
            if key in self.queue_child_fds:
                continue
            try:
                before, fd = bound_process(item["pid"])
            except (FileNotFoundError, ProcessLookupError):
                continue
            require(before == item, "QUEUE_DESCENDANT_CHANGED")
            self.queue_child_fds[key] = fd
            known[key] = item
            changed = True
        if changed:
            self.evidence["queue_descendants"] = list(known.values())
            self.checkpoint()

    def stop_policy(self):
        raw = self.execute(["/usr/bin/systemctl", "show", QUEUE, "--property=SendSIGKILL,TimeoutStopUSec"])
        values = dict(line.split("=", 1) for line in raw.decode().splitlines())
        require(set(values) == {"SendSIGKILL", "TimeoutStopUSec"} and values["SendSIGKILL"] in ("yes", "no"), "QUEUE_STOP_POLICY_UNVERIFIED")
        return values

    def override_payload(self):
        return ("# kmj-storage-" + self.evidence["nonce"] + "\n[Service]\nSendSIGKILL=no\nTimeoutStopSec=infinity\n").encode()

    def override_directory(self):
        from orchestrator import protected_dir
        parent = protected_dir("/run/systemd/system")
        try:
            name = QUEUE + ".d"
            try:
                os.mkdir(name, 0o700, dir_fd=parent)
                os.fsync(parent)
            except FileExistsError:
                pass
            fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
            info = os.fstat(fd)
            require(info.st_uid == 0 and not info.st_mode & 0o022, "QUEUE_OVERRIDE_DIRECTORY_UNSAFE")
            return fd
        finally:
            os.close(parent)

    def install_queue_stop_override(self):
        self.marker_bound()
        self.maintenance_probe(True)
        replacement = self.evidence["queue_replacement"]
        require(p.process(replacement["pid"]) == replacement, "QUEUE_REPLACEMENT_CHANGED")
        processes = all_processes()
        require(not any(x["ppid"] == replacement["pid"] for x in processes.values()), "QUEUE_REPLACEMENT_HAS_CHILDREN")
        cg = self.evidence["original_units"][QUEUE]["ControlGroup"]
        require(cgroup_members(cg) == {replacement["pid"]}, "QUEUE_CGROUP_HAS_OTHER_PROCESSES")
        self.evidence["stop_policy_original"] = self.stop_policy()
        self.evidence["stop_override"] = {"name": "zzzz-kmj-storage-" + self.evidence["nonce"] + ".conf", "inode": None}
        self.checkpoint()  # WAL before creation or metadata reload.
        directory = self.override_directory()
        try:
            fd = os.open(self.evidence["stop_override"]["name"], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                         0o600, dir_fd=directory)
            try:
                write_all(fd, self.override_payload())
                os.fsync(fd)
                self.evidence["stop_override"]["inode"] = stamp(os.fstat(fd))
                self.checkpoint()
            finally:
                os.close(fd)
            os.fsync(directory)
        finally:
            os.close(directory)
        self.execute(["/usr/bin/systemctl", "daemon-reload"])
        require(self.stop_policy() == {"SendSIGKILL": "no", "TimeoutStopUSec": "infinity"}, "QUEUE_SAFE_STOP_OVERRIDE_NOT_EFFECTIVE")
        self.evidence["stop_override_effective"] = True
        self.checkpoint()

    def remove_queue_stop_override(self):
        values, _ = p.properties(QUEUE)
        cg = self.evidence["original_units"][QUEUE]["ControlGroup"]
        require(self.unit_empty(QUEUE, values), "QUEUE_NOT_QUIESCENT_RETAIN_SAFE_STOP_OVERRIDE")
        directory = self.override_directory()
        try:
            name = self.evidence["stop_override"]["name"]
            try:
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            except FileNotFoundError:
                require(self.evidence.get("stop_override_remove_intent") is True, "QUEUE_OVERRIDE_MISSING")
            else:
                try:
                    info = os.fstat(fd)
                    require(stamp(info) == self.evidence["stop_override"]["inode"] and info.st_uid == 0
                            and stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and stat.S_IMODE(info.st_mode) == 0o600
                            and os.read(fd, 4096) == self.override_payload(), "QUEUE_OVERRIDE_OWNERSHIP_CHANGED")
                finally:
                    os.close(fd)
                self.evidence["stop_override_remove_intent"] = True
                self.checkpoint()
                os.unlink(name, dir_fd=directory)
                os.fsync(directory)
        finally:
            os.close(directory)
        self.execute(["/usr/bin/systemctl", "daemon-reload"])
        require(self.stop_policy() == self.evidence["stop_policy_original"], "QUEUE_PRIOR_STOP_POLICY_NOT_RESTORED")
        self.evidence["stop_override_removed"] = True
        self.checkpoint()

    def fpm_children(self):
        master = self.evidence["fpm_master"]
        require(p.process(master["pid"]) == master, "FPM_MASTER_CHANGED")
        processes = all_processes()
        result = {}
        for pid, item in processes.items():
            if self.account.pw_uid not in item["uids"]:
                continue
            require(item["ppid"] == master["pid"] and item["args"] == ["php-fpm: pool " + POOL]
                    and item["exe"] == master["exe"] and item["uids"] == [self.account.pw_uid] * 4
                    and item["netns"] == self.evidence["netns"]
                    and p.owns_socket(pid, self.evidence["listener_inode"]), "UNKNOWN_PRODUCTION_WRITER_OR_DESCENDANT")
            result[pid] = item
        return result

    def socket_empty(self):
        listeners = p.production_listeners(Path("/proc/net/tcp").read_text())
        require(len(listeners) == 1 and listeners[0]["inode"] == self.evidence["listener_inode"], "FPM_LISTENER_CHANGED")
        pending = False
        for filename in ("/proc/net/tcp", "/proc/net/tcp6"):
            for line in Path(filename).read_text().splitlines()[1:]:
                fields = line.split()
                require(len(fields) >= 10, "TCP_STATE_UNREADABLE")
                if (fields[1].endswith(":525C") or fields[2].endswith(":525C")) and fields[3] in ("01", "02", "03"):
                    pending = True
        return listeners[0]["backlog"] == 0 and not pending

    def drain_fpm(self):
        self.guard_counter()
        initial = self.fpm_children()
        self.evidence["fpm_children"] = list(initial.values())
        self.checkpoint()
        for pid, item in initial.items():
            bound, fd = bound_process(pid)
            require(bound == item, "FPM_CHILD_CHANGED")
            self.fpm_fds[pid] = fd
        def done():
            self.guard_counter()
            current = self.fpm_children()
            require(set(current) <= set(initial), "FPM_REPLACEMENT_CHILD")
            for pid, item in current.items():
                require(item == initial[pid], "FPM_CHILD_IDENTITY_CHANGED")
            return not current and all(exited(fd) for fd in self.fpm_fds.values()) and self.socket_empty()
        self.wait(done)
        self.flags.update(all_fpm_pidfds_exited=True, no_untracked_fpm_descendants=True,
                          no_replacement_fpm_children=True, fpm_master_listener_unchanged=True,
                          tcp_syn_established_empty=True, listen_backlog_zero=True)

    def maintenance_off(self):
        self.guard_counter()
        require(not self.fpm_children(), "SERVICE_WRITER_REAPPEARED")
        self.marker_bound()
        # unlinkat acts on the retained directory, never follows final symlink.
        os.unlink("down", dir_fd=self.marker_dir)
        os.fsync(self.marker_dir)
        self.evidence["marker_removed"] = True
        self.checkpoint()
        self.maintenance_probe(False)

    def drain_proofs(self):
        self.guard_counter()
        scheduler = self.evidence["original_units"][SCHEDULER]["ControlGroup"]
        queue = self.evidence["original_units"][QUEUE]["ControlGroup"]
        require(self.unit_empty(SCHEDULER) and self.unit_empty(QUEUE) and not self.fpm_children() and self.socket_empty(), "DRAIN_STATE_CHANGED")
        result = {key: self.flags.get(key, False) for key in DRAIN}
        result["guard_identity_readback"] = True
        return result

    def scanner_run(self, command, plan_id=None):
        require(command in {"plan", "switch", "rollback"}, "SCANNER_OPERATION_NOT_ALLOWED")
        raw = p.read_file(p.DEPENDENCIES["scanner"], protected=True)
        require(p.digest(raw) == PINS["scanner"], "SCANNER_PIN_CHANGED")
        # Execute checked bytes from a sealed private memfd; never reread a
        # candidate pathname after verifying content.
        fd = os.memfd_create("verified-storage-switch", os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
        try:
            write_all(fd, raw)
            fcntl.fcntl(fd, F_ADD_SEALS, ALL_SEALS)
            args = ["/usr/bin/python3", "-I", "-B", f"/proc/self/fd/{fd}", command,
                    "--app-dir", str(TARGET_APP), "--shared", SHARED, "--state-dir", SCANNER_STATE]
            if command == "switch":
                require(re.fullmatch(r"[a-f0-9]{16}", plan_id or ""), "PLAN_ID_INVALID")
                args.extend(["--apply", "--plan-id", plan_id])
            elif command == "rollback":
                require(plan_id is None, "ROLLBACK_TAKES_NO_PLAN")
                args.append("--apply")
            self.release_lock.verify()
            require(self.release_lock.fd is not None, "RELEASE_LOCK_NOT_HELD")
            value = subprocess.run(args, pass_fds=[fd, self.release_lock.fd], stdin=subprocess.DEVNULL, capture_output=True,
                                   env=TOOL_ENV, timeout=MAX_DRAIN, check=True)
            require(len(value.stdout) <= 1048576, "SCANNER_OUTPUT_TOO_LARGE")
            return json.loads(value.stdout, object_pairs_hook=no_duplicates)
        finally:
            os.close(fd)

    def fresh_plan(self):
        self.drain_proofs()
        require(self.evidence.get("marker_removed") is True and not os.path.lexists(APP / "storage/framework/down"), "MAINTENANCE_STILL_PRESENT")
        value = self.scanner_run("plan")
        require(value.get("command") == "plan" and value.get("mutated") is False and value.get("persistent_only_plan_id") is True
                and value.get("ready") is True and not value.get("persistent_conflicts"), "V6_FRESH_PLAN_NOT_READY")
        return {"ready": True, "plan_id": value["plan_id"]}

    def switch(self, plan_id):
        self.drain_proofs()
        value = self.scanner_run("switch", plan_id)
        require(value.get("status") == "OK" and value.get("command") == "switch", "V6_SWITCH_UNCERTAIN")
        self.evidence["switch_result"] = value
        self.checkpoint()

    def writers_still_paused(self):
        """Fresh proof that the transaction still owns admission: guard intact,
        timer stopped, scheduler and queue cgroups empty, no FPM writer, no
        pending FastCGI connection. Never re-drains live traffic."""
        self.pointer()
        self.release_lock.verify()
        self.guard_counter()
        require(p.properties(TIMER)[0]["ActiveState"] == "inactive"
                and self.unit_empty(SCHEDULER) and self.unit_empty(QUEUE)
                and not self.fpm_children() and self.socket_empty(), "WRITERS_NOT_PAUSED")
        return True

    def rollback_storage(self):
        require(self.writers_still_paused() is True, "WRITERS_NOT_PAUSED")
        self.evidence["rollback_kept"] = self.snapshot_name(TARGET_APP)
        self.checkpoint()  # binds a crashed rollback journal to this exact preserved name
        value = self.scanner_run("rollback")
        require(value.get("status") == "OK" and value.get("command") == "rollback", "V6_ROLLBACK_UNCERTAIN")
        self.evidence["rollback_result"] = value
        self.checkpoint()

    def snapshot_name(self, app):
        names = [entry.name for entry in Path(app).iterdir() if entry.name.startswith("storage.pre-shared-")]
        require(len(names) == 1 and re.fullmatch(r"storage\.pre-shared-[0-9]{8}T[0-9]{6}Z", names[0]), "SNAPSHOT_AMBIGUOUS")
        return names[0]

    def completed_receipt(self, app, name):
        from orchestrator import protected_dir
        helper, scanner = self.module("helper"), self.module("scanner")
        directory = protected_dir(SCANNER_STATE)
        try:
            info = os.fstat(directory)
            require(stat.S_IMODE(info.st_mode) == 0o700, "SCANNER_STATE_NOT_PRIVATE")
            key = p.digest(str(app).encode())[:12]
            require(key + ".journal" not in os.listdir(directory), "ACTIVE_SCANNER_JOURNAL")
            matching = []
            for entry in os.listdir(directory):
                if re.fullmatch(re.escape(key) + r"\.journal\.done-[0-9]+", entry):
                    records = helper.receipt_entries(directory, entry, scanner)
                    if records and records[0].get("kept") == name:
                        matching.append(records)
            # v6 recover archives a successfully thawed transaction at
            # "verified". The snapshot attestor independently checks thaw.
            require(len(matching) == 1 and matching[0][-1].get("phase") in {"verified", "complete"},
                    "NO_COMPLETED_SCANNER_RECEIPT")
            return matching[0]
        finally:
            os.close(directory)

    def switched_proofs(self):
        self.pointer()
        helper = self.module("helper")
        candidate_name = self.snapshot_name(TARGET_APP)
        records = self.completed_receipt(TARGET_APP, candidate_name)
        state = self.store.read()
        require(state is not None and records[0].get("plan") == state.get("plan_id"),
                "CANDIDATE_RECEIPT_WRONG_PLAN")
        require((APP / "storage").is_symlink()
                and os.readlink(APP / "storage") == SHARED, "LIVE_LINK_CHANGED")
        helper.attest_snapshot(str(TARGET_APP), SHARED, candidate_name, CANDIDATE_SHA,
                               SCANNER_STATE, release_root=CANDIDATE,
                               scanner_path=p.DEPENDENCIES["scanner"])
        self.pointer()
        return dict.fromkeys(SWITCHED, True)

    def bind_recovery(self, state):
        evidence = state.get("recovery_evidence")
        require(type(evidence) is dict and re.fullmatch(r"[a-f0-9]{32}", evidence.get("nonce", "")), "RECOVERY_NONCE_INVALID")
        base = {"nonce", "netns", "live_sha", "queue_original", "original_units", "fpm_master", "listener_inode",
                "pool", "nginx_uid", "ruleset_sha256", "guard_priority", "marker",
                "maintenance_initially_absent", "original_storage", "maintenance_storage",
                "queue_descendants", "live_shared_inode"}
        optional = {"environment", "marker_directory", "maintenance_time", "guard_installed", "guard_remove_intent", "guard_removed", "restart_requested",
                    "queue_replacement", "stop_policy_original", "stop_override", "stop_override_effective", "stop_override_remove_intent", "stop_override_removed",
                    "fpm_children", "marker_removed", "switch_result", "rollback_kept", "rollback_result"}
        require(base <= set(evidence) <= base | optional and evidence["maintenance_initially_absent"] is True
                and evidence["netns"] == p.namespace() == p.namespace(1)
                and evidence["live_sha"] == LIVE_SHA, "RECOVERY_EVIDENCE_SCHEMA_INVALID")
        self.evidence = evidence
        require(state["guard"] == self.guard_identity(), "RECOVERY_GUARD_IDENTITY_MISMATCH")
        self.pointer()
        self.module("helper").git_identity(Path(LIVE), evidence["live_sha"])
        self.module("helper").git_identity(Path(CANDIDATE), CANDIDATE_SHA)
        # Existing v6 child retains this same global lock FD after parent death.
        # Also require app flock not busy; never recover across active scanner.
        fd = os.open(TARGET_APP, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        finally:
            os.close(fd)
        if "environment" in evidence:
            metadata = evidence["environment"]
            require(set(metadata) == {"name", "sha256"} and metadata["name"] in {
                "queue-environment-" + evidence["nonce"] + suffix + ".json" for suffix in ("", "-replacement")}, "RECOVERY_ENVIRONMENT_NAME_INVALID")
            fd = os.open(metadata["name"], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self.store.fd)
            try:
                info = os.fstat(fd)
                require(info.st_uid == 0 and info.st_nlink == 1 and stat.S_ISREG(info.st_mode)
                        and stat.S_IMODE(info.st_mode) == 0o600 and info.st_size <= 1048576, "RECOVERY_ENVIRONMENT_UNSAFE")
                raw = os.read(fd, 1048577)
                require(p.digest(raw) == metadata["sha256"], "RECOVERY_ENVIRONMENT_HASH_MISMATCH")
                self.env = json.loads(raw, object_pairs_hook=no_duplicates)
                require(type(self.env) is dict and all(type(k) is type(v) is str and "\0" not in k + v for k, v in self.env.items()), "RECOVERY_ENVIRONMENT_INVALID")
            finally:
                os.close(fd)
        if evidence.get("stop_override") and not evidence.get("stop_override_removed"):
            values, _ = p.properties(QUEUE)
            cg = evidence["original_units"][QUEUE]["ControlGroup"]
            require(self.unit_empty(QUEUE, values), "QUEUE_NOT_QUIESCENT_RETAIN_OVERRIDE_AND_GUARD")
            # Removal is deliberately not hidden inside bind's read-only phase.
        return True

    def reconcile_storage_readonly(self):
        self.pointer()
        from orchestrator import protected_dir
        directory = protected_dir(SCANNER_STATE)
        try:
            key = p.digest(str(TARGET_APP).encode())[:12]
            if key + ".journal" in os.listdir(directory):
                # Actual v6 recover needs its own reviewed explicit recovery
                # invocation. Never guess an unfinished immutable freeze here.
                return "uncertain"
        finally:
            os.close(directory)
        if stat.S_ISDIR((TARGET_APP / "storage").lstat().st_mode) and self.original_storage_writable_and_unchanged():
            return "verified_original"
        try:
            self.switched_proofs()
            return "verified_switched"
        except (OSError, Blocked, ValueError, self.module("helper").Rejected):
            return "uncertain"

    def recover_active_scanner(self, state):
        """Recover only a switch journal bound to this paused transaction."""
        if state["phase"] not in {"switch_intent", "recovery_required", "intent_rollback"} or not state.get("plan_id"):
            return False
        rollback_kept = self.evidence.get("rollback_kept") if state.get("rollback_intent") else None
        self.pointer()
        self.release_lock.verify()
        self.guard_counter()
        require(p.properties(TIMER)[0]["ActiveState"] == "inactive"
                and self.unit_empty(SCHEDULER) and self.unit_empty(QUEUE)
                and not self.fpm_children() and self.socket_empty(), "RECOVERY_WRITERS_NOT_PAUSED")
        scanner = self.module("scanner")
        original_read = scanner.journal_read

        def bound_read(context):
            entries, offset, exists = original_read(context)
            phases = ["begin", "live_frozen", "both_frozen", "link_created",
                      "exchanged", "preserved", "verified", "complete"]
            rollback = ["rollback_begin", "rollback_shared_frozen", "rollback_old_thawed",
                        "rollback_exchanged", "rollback_parked"]
            observed = [entry["phase"] for entry in entries]
            require(exists and entries, "RECOVERY_JOURNAL_NOT_BOUND")
            if observed[0] == "rollback_begin":
                # Only a rollback this transaction recorded, for the exact preserved name.
                require(rollback_kept is not None and observed == rollback[:len(observed)]
                        and all(entry.get("kept") == rollback_kept for entry in entries), "RECOVERY_JOURNAL_NOT_BOUND")
            else:
                require(observed in (phases[:len(observed)],
                        [phase for phase in phases if phase != "preserved"][:len(observed)])
                        and entries[0].get("plan") == state["plan_id"], "RECOVERY_JOURNAL_NOT_BOUND")
            return entries, offset, exists

        scanner.journal_read = bound_read
        try:
            result = scanner.cmd_recover(types.SimpleNamespace(
                app_dir=str(TARGET_APP), shared=SHARED, state_dir=SCANNER_STATE,
                allowed_root="/home/kmjprod", proc_root="/proc", apply=True))
            require(result.get("status") == "OK" and result.get("mutated") is True,
                    "SCANNER_RECOVERY_NOT_CONFIRMED")
        finally:
            scanner.journal_read = original_read
            while scanner._LOCKS:
                os.close(scanner._LOCKS.pop())
        return True

    def original_storage_writable_and_unchanged(self):
        self.pointer()
        scanner = self.module("scanner")
        fd = os.open(TARGET_APP / "storage", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            require(stamp(os.fstat(fd)) == self.evidence["original_storage"], "ORIGINAL_STORAGE_IDENTITY_CHANGED")
            require(scanner.tree_clean(fd, True), "ORIGINAL_STILL_IMMUTABLE")
            def no_append(child):
                require(not scanner.FREEZER.flags(child) & scanner.FS_APPEND_FL, "ORIGINAL_APPEND_ONLY")
                return False
            scanner._visit_tree(fd, True, no_append)
            return True
        finally:
            os.close(fd)

    def restore_owned_maintenance(self, state):
        if self.evidence.get("stop_override") and not self.evidence.get("stop_override_removed"):
            self.remove_queue_stop_override()
        marker = Path(self.evidence["maintenance_storage"]) / "framework/down"
        if not os.path.lexists(marker):
            return
        require(self.evidence.get("marker") is not None and self.env is not None, "UNBOUND_MAINTENANCE_MARKER_RETAINED")
        require(self.original_storage_writable_and_unchanged() is True, "ORIGINAL_STORAGE_NOT_SAFE_FOR_ADMISSION")
        self.open_marker_directory()
        self.marker_bound()
        # Verified-original abort restores admission to the unchanged writable
        # physical inode. A running job need not be stopped to remove our own
        # marker; override restoration above still requires inactive+empty.
        os.unlink("down", dir_fd=self.marker_dir)
        os.fsync(self.marker_dir)
        self.evidence["marker_removed"] = True
        self.checkpoint()

    def restore_units(self, original):
        require(set(original) == set(UNITS), "RESUME_UNIT_SCOPE_INVALID")
        self.pointer()
        require(not self.evidence.get("stop_override") or self.evidence.get("stop_override_removed") is True,
                "SAFE_STOP_OVERRIDE_MUST_BE_RESTORED_WHILE_QUEUE_EMPTY")
        for unit in (QUEUE, TIMER):
            require(original[unit] in ("active", "inactive"), "RESUME_UNIT_STATE_INVALID")
            if original[unit] == "active":
                self.systemctl("start", unit)
        # Scheduler oneshot was originally inactive. Never start it explicitly.
        require(original[SCHEDULER] == "inactive", "SCHEDULER_ORIGINAL_STATE_CHANGED")

    def runtime_restored(self, original):
        def ready():
            values = {unit: p.properties(unit)[0] for unit in (QUEUE, TIMER)}
            if not all(values[unit]["ActiveState"] == original[unit] for unit in values):
                return False
            if original[QUEUE] == "active":
                pid = int(values[QUEUE]["MainPID"])
                if not pid:
                    return False
                item = p.process(pid)
                self.verify_queue(item)
                env = parse_environment(p.read_file(f"/proc/{pid}/environ"))
                require(application_environment(env) == application_environment(self.env), "RESUMED_QUEUE_ENVIRONMENT_CHANGED")
                self.env = env
                self.maintenance_probe(False)
            return True
        self.wait(ready, 30)
        return True

    def remove_owned_guard(self):
        if self.guard_absent():
            require(not self.evidence.get("guard_installed") or self.evidence.get("guard_remove_intent") is True,
                    "OWNED_GUARD_DISAPPEARED_UNEXPECTEDLY")
            raw, _ = p.command(["/usr/sbin/nft", "-j", "list", "ruleset"])
            require(ruleset_identity(raw) == self.evidence["ruleset_sha256"], "ABSENT_GUARD_BASELINE_CHANGED")
            self.evidence["guard_removed"] = True
            self.checkpoint()
            return
        try:
            self.guard_counter()
        except Blocked as exc:
            # A different nft JSON rendering of OUR rule must not strand production
            # behind the admission guard. Delete only the transaction-owned table
            # (128-bit nonce name, install recorded) whose sole chain is our hook.
            require(str(exc).startswith(("GUARD_EXPRESSION_CHANGED", "GUARD_RULE_CHANGED"))
                    and self.evidence.get("guard_installed") is True and self.owned_table_shape_only(), str(exc))
        self.evidence["guard_remove_intent"] = True
        self.checkpoint()
        self.execute(["/usr/sbin/nft", "delete", "table", "inet", self.guard_identity()["table"]])
        self.evidence["guard_removed"] = True
        self.checkpoint()

    def owned_table_shape_only(self):
        """Our nonce table holds exactly one base chain 'out' at our output hook/priority and one rule
        carrying our nonce comment; nothing else (no sets, maps, other chains)."""
        guard = self.guard_identity()
        doc = json.loads(self.execute(["/usr/sbin/nft", "-j", "list", "table", "inet", guard["table"]]),
                         object_pairs_hook=no_duplicates)
        kinds = [next(iter(record)) for record in doc["nftables"] if "metainfo" not in record]
        chains = [record["chain"] for record in doc["nftables"] if "chain" in record]
        rules = [record["rule"] for record in doc["nftables"] if "rule" in record]
        return (sorted(kinds) == ["chain", "rule", "table"] and len(chains) == len(rules) == 1
                and chains[0].get("name") == "out" and chains[0].get("hook") == "output"
                and chains[0].get("prio") == guard["priority"] and chains[0].get("type") == "filter"
                and rules[0].get("chain") == "out" and rules[0].get("comment") == guard["comment"])

    def guard_absent(self):
        raw, _ = p.command(["/usr/sbin/nft", "-j", "list", "ruleset"])
        table = self.guard_identity()["table"]
        return not any(record.get("table", {}).get("name") == table for record in json.loads(raw)["nftables"])


def materialize(request):
    """Called only outside the released global lock, never from error unwind."""
    require(request == {"candidate_sha": CANDIDATE_SHA, "expected_live": LIVE,
                        "materializer_sha256": PINS["materializer"]}, "MATERIALIZER_REQUEST_INVALID")
    require(str(Path("/home/kmjprod/current").resolve(strict=True)) == LIVE, "POINTER_CHANGED")
    raw = p.read_file(p.MATERIALIZER_SOURCE, protected=True)
    require(p.digest(raw) == PINS["materializer"], "MATERIALIZER_PIN_CHANGED")
    fd = os.memfd_create("verified-materializer", os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
    try:
        write_all(fd, raw)
        fcntl.fcntl(fd, F_ADD_SEALS, ALL_SEALS)
        p.read_file(str(Path("/usr/bin/bash").resolve(strict=True)), 64 * 1048576, protected=True)
        result = subprocess.run(["/usr/bin/bash", "-p", f"/proc/self/fd/{fd}", CANDIDATE_SHA, Path(LIVE).name],
                       pass_fds=[fd], env=TOOL_ENV, stdin=subprocess.DEVNULL,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=MAX_DRAIN, check=True)
    finally:
        os.close(fd)
    require(str(Path("/home/kmjprod/current").resolve(strict=True)) == LIVE, "POINTER_CHANGED_AFTER_MATERIALIZER")
    required = {b"KMJ_MATERIALIZE=PASS", b"KMJ_MATERIALIZE_SHARED=PASS", b"RUNTIME_ENV=BYTE_IDENTICAL",
                b"NGINX_PUBLIC_ACL=PASS", b"NGINX_PRIVATE_ENV=DENIED"}
    require(required <= set(result.stdout.splitlines()), "MATERIALIZER_COMPLETION_NOT_REPORTED")
    return {"materializer_completed": True, "pointer_bce_unchanged": True,
            "runtime_env_byte_identical": True, "nginx_public_readable": True, "nginx_env_unreadable": True,
            "materializer_sha256": PINS["materializer"]}
