"""Host-free, credential-free contracts for the A2b unit/identity comparison."""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "scripts/operations/compare-offsite-unit-identity-20261031.py"
spec = importlib.util.spec_from_file_location("a2b", SRC)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

FPA = "SHA256:" + "A" * 43
FPB = "SHA256:" + "B" * 43
SECRET = "SECRET-MARKER-/root/.ssh/id_rsa"


def make(exec_body=b"#!/bin/sh\n. /etc/kmj-codebridge/offsite-sftp.conf\n", props=None, allowfile=b"%s\n" % FPA.encode(),
         fp=FPA, key=b"PRIVATE", confbody=None):
    props = props or {}
    exe = Path("/usr/local/sbin/offsite.sh")
    keyp = Path("/etc/kmj-codebridge/key")
    confb = confbody if confbody is not None else (b"HOST=h\nIDENTITY_FILE=" + str(keyp).encode() + b"\n")

    def show(name):
        d = {"LoadState": "loaded", "DropInPaths": "", "ExecStart": f"{{ path={exe} ; argv[]={exe} ; }}"}
        d.update(props)
        return d.get(name)

    def reader(path, *, maxsize, private, **_):
        if path == exe: return exec_body
        if path == m.CONF: return confb
        if path == keyp: return key
        if path == m.ALLOW: return allowfile
        return None
    return dict(show=show, reader=reader, fingerprint=lambda _k: fp)


class Compare(unittest.TestCase):
    def test_clean_service_with_unauthorized_key_makes_repair_precondition(self):
        r = m.compare(**make(fp=FPB))
        self.assertEqual(r["service_identity_source"], "SFTP_CONFIG_ONLY")
        self.assertEqual(r["authorized_fingerprint_match"], "NO")
        self.assertEqual(r["repair_precondition_met"], "YES")

    def test_authorized_key_means_no_repair_precondition(self):
        r = m.compare(**make())
        self.assertEqual(r["authorized_fingerprint_match"], "YES")
        self.assertEqual(r["repair_precondition_met"], "NO")

    def test_dropin_embedded_key_or_multiple_execstart_is_not_proven(self):
        for kw in (dict(props={"DropInPaths": "/etc/systemd/system/x.d/o.conf"}),
                   dict(exec_body=b"ssh -i /root/.ssh/id_rsa host\n. /etc/kmj-codebridge/offsite-sftp.conf\n"),
                   dict(props={"ExecStart": "{ path=/a ; } { path=/b ; }"}),
                   dict(exec_body=b"#!/bin/sh\necho no config\n")):
            with self.subTest(kw=list(kw)):
                r = m.compare(**make(**kw))
                self.assertEqual(r["service_identity_source"], "NOT_PROVEN")
                self.assertEqual(r["repair_precondition_met"], "NO")

    def test_missing_allowlist_or_unreadable_key_is_unknown_never_no(self):
        self.assertEqual(m.compare(**make(allowfile=None))["authorized_fingerprint_match"], "UNKNOWN_NO_OWNER_ALLOWLIST")
        r = m.compare(**make(fp=None))
        self.assertEqual(r["authorized_fingerprint_match"], "UNKNOWN")
        self.assertEqual(r["repair_precondition_met"], "NO")
        self.assertEqual(m.compare(**make(allowfile=b"not-a-fingerprint\n"))["authorized_fingerprint_match"], "UNKNOWN_NO_OWNER_ALLOWLIST")

    def test_duplicate_or_relative_identity_in_config_is_invalid(self):
        for body in (b"IDENTITY_FILE=/a\nIDENTITY_FILE=/b\n", b"IDENTITY_FILE=../x\n", b"IDENTITY_FILE=rel\n"):
            self.assertEqual(m.compare(**make(confbody=body))["config_identity_present"], "NO_OR_INVALID")

    def test_output_never_contains_paths_or_secrets_and_is_read_only(self):
        r = m.compare(**make(key=SECRET.encode()))
        text = "\n".join(f"{k}={v}" for k, v in r.items())
        for bad in ("/usr/local", "/etc/", "/root", "SECRET", "HOST=", "h\n"):
            self.assertNotIn(bad, text)
        self.assertEqual(r["mutations"], "NONE")
        self.assertEqual(r["backup_created"], "NOT_VERIFIED")
        self.assertEqual(r["restore_verified"], "NO")

    def test_protected_reader_rejects_symlink_loose_mode_hardlink_and_big_files(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", str(d)]))
        os.chmod(d, 0o755)
        uid = os.getuid()
        f = d / "f"; f.write_bytes(b"x"); os.chmod(f, 0o600)
        self.assertEqual(m.read_protected(f, uid=uid, maxsize=10, private=True, stop=d), b"x")
        os.chmod(f, 0o644)
        self.assertIsNone(m.read_protected(f, uid=uid, maxsize=10, private=True, stop=d))
        self.assertEqual(m.read_protected(f, uid=uid, maxsize=10, private=False, stop=d), b"x")
        os.chmod(f, 0o666)
        self.assertIsNone(m.read_protected(f, uid=uid, maxsize=10, private=False, stop=d))
        os.chmod(f, 0o600)
        os.symlink(f, d / "l"); os.link(f, d / "h")
        self.assertIsNone(m.read_protected(d / "l", uid=uid, maxsize=10, private=True, stop=d))
        self.assertIsNone(m.read_protected(f, uid=uid, maxsize=10, private=True, stop=d))  # nlink 2
        os.unlink(d / "h")
        self.assertIsNone(m.read_protected(f, uid=uid, maxsize=0, private=True, stop=d))
        os.chmod(d, 0o777)
        self.assertIsNone(m.read_protected(f, uid=uid, maxsize=10, private=True, stop=d))

    def test_source_is_static_read_only(self):
        t = SRC.read_text()
        for bad in ("shell=True", "os.system", "urllib", "socket", "requests", "systemctl\", \"restart", ".write"):
            self.assertNotIn(bad, t)
        import re
        self.assertIsNone(re.search(r"(?<!os\.)\bopen\(", t))  # only the no-follow os.open descriptor path
        self.assertIn("A2B_COMPARE=BLOCKED_HOST_ROOT_OR_ARGUMENTS", t)

    def test_cli_refuses_arguments_and_non_root_off_host(self):
        r = subprocess.run([sys.executable, "-I", str(SRC), "x"], capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout.strip()), (2, "A2B_COMPARE=BLOCKED_HOST_ROOT_OR_ARGUMENTS"))


if __name__ == "__main__":
    unittest.main()
