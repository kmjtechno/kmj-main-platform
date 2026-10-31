"""Host-free contracts for the A2c effective-identity trace (no credentials, no network, no root)."""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "scripts/operations/trace-offsite-effective-identity-20261031.py"
spec = importlib.util.spec_from_file_location("a2c", SRC)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
FPA, FPB = "SHA256:" + "A" * 43, "SHA256:" + "B" * 43


def rows(by_path):
    def c(p, uid_ok, run=None):
        return by_path.get(str(p), {"id": m.pid(p), "kind": "MISSING", "role": "NONE", "fps": [], "env_keys": []})
    return c


def show_factory(**over):
    d = {"User": "root", "DropInPaths": "", "EnvironmentFiles": "", "ExecStart": "{ path=/usr/local/sbin/b.sh ; }"}
    d.update(over)
    return lambda k: d.get(k)


def key_row(p, fp=FPA, role="PRIVATE_KEY"):
    return {"id": m.pid(p), "kind": "FILE", "role": role, "fps": [fp], "env_keys": []}


class Trace(unittest.TestCase):
    body = lambda self, b: (lambda p: ("FILE", b))

    def run_trace(self, body=b"#!/bin/sh\nsftp host\n", cands=None, allow=None, **over):
        return m.trace(show=show_factory(**over), read_body=self.body(body), classify_fn=rows(cands or {}),
                       home_of=lambda u: "/root", allow_raw=allow)

    def test_default_home_key_is_the_single_unproven_candidate(self):
        k = "/root/.ssh/id_ed25519"
        r = self.run_trace(cands={k: key_row(Path(k))})
        self.assertEqual(r["effective_identity"], "SINGLE_CANDIDATE_UNPROVEN")
        self.assertEqual(r["candidate_fingerprints"], FPA)
        self.assertEqual(r["tools_referenced"], "sftp")
        self.assertEqual(r["remote_auth_witnessed"], "NO")
        self.assertEqual(r["repair_allowed"], "NO")

    def test_two_keys_or_dropin_is_ambiguous_never_single(self):
        a, b = "/root/.ssh/id_ed25519", "/root/.ssh/id_rsa"
        r = self.run_trace(cands={a: key_row(Path(a)), b: key_row(Path(b), FPB)})
        self.assertEqual(r["effective_identity"], "AMBIGUOUS_OR_UNPROVEN")
        r = self.run_trace(cands={a: key_row(Path(a))}, DropInPaths="/etc/systemd/system/x.d/o.conf")
        self.assertEqual(r["effective_identity"], "AMBIGUOUS_OR_UNPROVEN")

    def test_ssh_config_identityfile_in_executable_path_is_a_candidate(self):
        body = b"ssh -F /etc/kmj-codebridge/ssh_config host\n"
        p = "/etc/kmj-codebridge/ssh_config"
        r = self.run_trace(body=body, cands={p: {"id": m.pid(p), "kind": "FILE", "role": "SSH_CONFIG", "fps": [FPB], "env_keys": []}})
        self.assertEqual(r["candidate_fingerprints"], FPB)
        self.assertEqual(r["referenced_paths_scanned"], "1")

    def test_none_found_and_allowlist_states(self):
        r = self.run_trace()
        self.assertEqual((r["effective_identity"], r["authorized_overlap"]), ("NONE_FOUND", "UNKNOWN_NO_OWNER_ALLOWLIST"))
        k = "/root/.ssh/id_rsa"
        c = {k: key_row(Path(k))}
        self.assertEqual(self.run_trace(cands=c, allow=FPA.encode())["authorized_overlap"], "YES")
        self.assertEqual(self.run_trace(cands=c, allow=FPB.encode())["authorized_overlap"], "NO")
        self.assertEqual(self.run_trace(cands=c, allow=b"garbage")["authorized_overlap"], "UNKNOWN_NO_OWNER_ALLOWLIST")

    def test_output_never_leaks_paths_values_or_secrets(self):
        k = "/root/.ssh/id_ed25519"
        body = b"#!/bin/sh\nsftp backup-user@secret.example.com # /etc/kmj-codebridge/offsite_secret_path\n"
        r = self.run_trace(body=body, cands={k: key_row(Path(k))})
        text = "\n".join(f"{a}={b}" for a, b in r.items())
        for bad in ("secret.example", "backup-user", "/etc/", "/root", "offsite_secret_path", "BEGIN"):
            self.assertNotIn(bad, text)
        self.assertEqual(r["mutations"], "NONE")

    def test_classify_real_files(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", str(d)]))
        os.chmod(d, 0o755)
        uid = (os.getuid(),)
        env = d / "env"; env.write_text("OFFSITE_HOST=h\nSSH_KEY=/k\nSECRETVAL=zz\n"); os.chmod(env, 0o600)
        row = m.classify(env, uid)
        self.assertEqual((row["role"], row["env_keys"]), ("ENV_WITH_KEY_REF", ["OFFSITE_HOST", "SSH_KEY"]))
        self.assertNotIn("zz", str(row))
        loose = d / "loose"; loose.write_text("SSH_KEY=1\n"); os.chmod(loose, 0o666)
        self.assertEqual(m.classify(loose, uid)["kind"], "UNTRUSTED_OWNER_OR_MODE")
        os.symlink(env, d / "link")
        self.assertEqual(m.classify(d / "link", uid)["kind"], "SYMLINK")
        os.link(env, d / "hard")
        self.assertEqual(m.classify(env, uid)["kind"], "RACE_OR_HARDLINK")
        self.assertEqual(m.classify(d / "nope", uid)["kind"], "MISSING")

    def test_static_read_only_and_no_ssh_G_or_network(self):
        t = SRC.read_text()
        for bad in ("shell=True", "os.system", "urllib", "socket", "ssh\", \"-G", "ssh-keyscan", "restart", "os.write", ".write_text", "chmod", "unlink"):
            self.assertNotIn(bad, t)

    def test_cli_refuses_arguments(self):
        r = subprocess.run([sys.executable, "-I", str(SRC), "x"], capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout.strip()), (2, "A2C_TRACE=BLOCKED_HOST_ROOT_OR_ARGUMENTS"))


if __name__ == "__main__":
    unittest.main()
