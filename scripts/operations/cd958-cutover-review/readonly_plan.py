"""Native fixed-scope inventory only; no mutation commands or Git execution."""
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import subprocess

from orchestrator import Blocked, LIVE, PINS, UNITS, protected_dir, require

DEPENDENCIES = {
    "helper": "/usr/local/libexec/kmj-codebridge/main-platform-storage-snapshot-attest.py",
    "scanner": "/usr/local/libexec/kmj-codebridge/main-platform-storage-switch-v6.py",
    # Staged materializer is not a trusted execution path: require a protected
    # root-private copy before any eventual native adapter may invoke bash -p.
    "materializer": "/usr/local/libexec/kmj-codebridge/main-platform-candidate-materialize-v2.sh",
}
PROPERTIES = ("ActiveState", "SubState", "Type", "User", "Group", "MainPID", "ExecStart",
              "WorkingDirectory", "Environment", "EnvironmentFiles", "ControlGroup", "Restart",
              "KillMode", "TimeoutStopUSec", "Triggers", "TriggeredBy")


def protected_bytes(path, max_bytes=1048576):
    parent = protected_dir(Path(path).parent)
    try:
        fd = os.open(Path(path).name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                     dir_fd=parent)
        try:
            info = os.fstat(fd)
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == 0
                    and info.st_mode & 0o022 == 0 and info.st_size <= max_bytes, "UNSAFE_DEPENDENCY")
            result = b""
            while len(result) <= max_bytes:
                part = os.read(fd, 65536)
                if not part:
                    break
                result += part
            require(len(result) <= max_bytes, "DEPENDENCY_TOO_LARGE")
            return result
        finally:
            os.close(fd)
    finally:
        os.close(parent)


def output_priority(document):
    """Choose strictly after every current IPv4-relevant OUTPUT base chain.

    Fail closed for symbolic/unknown priority, unsupported hooked families,
    malformed records and exhausted integer priority space. Native apply must
    compare the full ruleset hash again immediately before guard insertion.
    """
    require(type(document) is dict and set(document) == {"nftables"}
            and type(document["nftables"]) is list, "NFT_SCHEMA_UNVERIFIED")
    priorities = []
    for record in document["nftables"]:
        require(type(record) is dict and len(record) == 1, "NFT_RECORD_UNVERIFIED")
        if "chain" not in record:
            continue
        chain = record["chain"]
        require(type(chain) is dict, "NFT_CHAIN_UNVERIFIED")
        if chain.get("hook") != "output":
            continue
        require(chain.get("family") in {"ip", "ip6", "inet", "arp", "bridge", "netdev"}, "NFT_FAMILY_UNVERIFIED")
        # Non-IP hooked families are not silently equated to inet priorities.
        require(chain["family"] not in {"bridge", "netdev"}, "NFT_NON_INET_OUTPUT_REVIEW")
        if chain["family"] not in {"ip", "inet"}:
            continue
        priority = chain.get("prio")
        require(type(priority) is int and -(2**31) <= priority < 2**31 - 1, "NFT_PRIORITY_UNVERIFIED")
        priorities.append(priority)
    return max(priorities + [-1]) + 1


def read_command(args):
    # Deliberately not a shell. Caller only uses root-protected system tools.
    protected_bytes(args[0], 32 * 1048576)
    value = subprocess.run(args, stdin=subprocess.DEVNULL, capture_output=True, check=True,
                           timeout=20, env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C",
                                           "HOME": "/nonexistent"})
    require(len(value.stdout) <= 4 * 1048576, "INVENTORY_TOO_LARGE")
    return value.stdout


def inventory():
    require(os.geteuid() == 0 and socket.gethostname().split(".")[0] == "KMJ-elite", "ROOT_ELITE_ONLY")
    require(str(Path("/home/kmjprod/current").resolve(strict=True)) == LIVE, "POINTER_CHANGED")
    self_ns = os.stat("/proc/self/ns/net")
    host_ns = os.stat("/proc/1/ns/net")
    require((self_ns.st_dev, self_ns.st_ino) == (host_ns.st_dev, host_ns.st_ino), "NOT_HOST_NETWORK_NAMESPACE")
    hashes = {key: hashlib.sha256(protected_bytes(path)).hexdigest() for key, path in DEPENDENCIES.items()}
    require(hashes == PINS, "PINNED_DEPENDENCIES_MISSING_OR_CHANGED")
    raw = read_command(["/usr/sbin/nft", "-j", "list", "ruleset"])
    ruleset = json.loads(raw)
    priority = output_priority(ruleset)
    units = {}
    for unit in UNITS:
        raw_unit = read_command(["/usr/bin/systemctl", "show", unit, "--property=" + ",".join(PROPERTIES)])
        values = dict(line.split("=", 1) for line in raw_unit.decode().splitlines() if "=" in line)
        require(set(values) == set(PROPERTIES), "UNIT_PROPERTIES_INCOMPLETE")
        # Do not emit raw Environment/ExecStart (may contain sensitive values).
        units[unit] = {key: values[key] for key in ("ActiveState", "SubState", "MainPID", "Type")}
        units[unit]["properties_sha256"] = hashlib.sha256(raw_unit).hexdigest()
    require(str(Path("/home/kmjprod/current").resolve(strict=True)) == LIVE, "POINTER_CHANGED")
    return {"mutated": False, "ready_for_apply": False, "native_adapter_complete": False,
            "ruleset_sha256": hashlib.sha256(raw).hexdigest(), "proposed_output_priority": priority,
            "network_namespace": [self_ns.st_dev, self_ns.st_ino], "dependencies": hashes,
            "units": units}
