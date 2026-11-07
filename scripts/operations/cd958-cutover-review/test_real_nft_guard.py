"""Real nftables: the exact guard script, readback parser, counter and owned-table delete.

Runs only inside a disposable network namespace (unshare -n) as root, so the host
ruleset is never touched. KMJ_REQUIRE_REAL_NFT=1 turns a missing capability into a failure."""
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REQUIRED = os.environ.get("KMJ_REQUIRE_REAL_NFT") == "1"

HARNESS = r'''
import fcntl, json, os, socket, struct, sys, types
from unittest.mock import Mock, patch
sys.path.insert(0, sys.argv[1])
import native_ops as n, orchestrator as o
# Bring loopback up inside the private namespace (SIOCSIFFLAGS IFF_UP|IFF_RUNNING).
fcntl.ioctl(socket.socket(), 0x8914, struct.pack("16sH", b"lo", 0x1 | 0x40))
real = n.subprocess.run
def nft(args, data=None, **_):
    return real(["nft", *args[1:]], input=data, capture_output=True, check=True).stdout
with patch.object(n.os, "fstat", return_value=types.SimpleNamespace(st_mode=0o40700, st_uid=0)), \
        patch.object(n.pwd, "getpwnam", return_value=types.SimpleNamespace(pw_uid=1000, pw_gid=1000)):
    ops = n.NativeOps(Mock(fd=0), Mock())
ops.evidence = {"nonce": os.urandom(16).hex(), "guard_priority": 1, "netns": [0, 0], "guard_installed": True}
ops.pointer = lambda: None
ops.checkpoint = lambda: None
ops.execute = lambda args, data=None, **_: nft(args, data)
with patch.object(n.p, "command", side_effect=lambda args: (nft(args), b"")):
    ops.execute(["/usr/sbin/nft", "-f", "-"], data=ops.guard_script())
    before = ops.guard_counter()
    s = socket.socket(); s.settimeout(2); refused = s.connect_ex(("127.0.0.1", 21084)); s.close()
    after = ops.guard_counter()
    shape = ops.owned_table_shape_only()
    present = not ops.guard_absent()
    ops.remove_owned_guard()
    print(json.dumps({"before": before, "after": after, "refused": refused, "shape": shape,
                      "present": present, "absent_after_remove": ops.guard_absent()}))
'''


def available():
    return os.geteuid() == 0 and shutil.which("nft") and shutil.which("unshare")


class RealNftGuardTests(unittest.TestCase):
    def test_exact_guard_round_trip_in_private_namespace(self):
        if not available():
            if REQUIRED:
                self.fail("real nft test required but root/nft/unshare unavailable")
            self.skipTest("needs root, nft and unshare")
        run = subprocess.run(["unshare", "-n", sys.executable, "-I", "-B", "-c", HARNESS, str(HERE)],
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stderr[-2000:])
        result = json.loads(run.stdout.strip().splitlines()[-1])
        self.assertEqual(result["refused"], 111)  # ECONNREFUSED from the tcp reset, no FastCGI bytes
        self.assertGreater(result["after"], result["before"])  # our counter saw the SYN
        self.assertTrue(result["shape"] and result["present"] and result["absent_after_remove"])


if __name__ == "__main__":
    unittest.main()
