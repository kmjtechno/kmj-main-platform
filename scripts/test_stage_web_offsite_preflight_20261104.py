"""Offline checks for exact KMJ stage web/legacy SSH readonly preflight."""
import ast
import importlib.util
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "scripts/operations/KMJ_STAGE_WEB_OFFSITE_PREFLIGHT_20261104.py"
spec = importlib.util.spec_from_file_location("kmj_stage_web_offsite", SOURCE)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


class StageWebAndOffsiteTests(unittest.TestCase):
    def test_source_parses(self):
        compile(SOURCE.read_text(), str(SOURCE), "exec")

    def test_exact_pins_and_no_mutators(self):
        s = SOURCE.read_text()
        for value in (
            "platform-574e443a2c75",
            "b2e69decab3acd861e94e11992cd8a4cff4f2b94",
            "/var/lib/kmj-main-platform-stage-releases",
            "/etc/kmj-codebridge/offsite-sftp.conf",
            "kmj-elite-offsite-backup.service",
            "STAGING_NGINX_ROUTING_AUTHORITY",
            "NOT_VERIFIED",
            "OFFSITE_SERVICE_CHANGES",
            "NONE",
        ):
            self.assertIn(value, s)
        tree = ast.parse(s)
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                functions.append(node.func.value.id + "." + node.func.attr)
        for name in ("os.chown", "os.fchown", "os.chmod", "os.mkdir", "os.unlink",
                     "os.remove", "os.symlink", "os.replace", "os.rename",
                     "os.system", "os.popen", "subprocess.Popen"):
            self.assertNotIn(name, functions)
        self.assertNotIn("shell=True", s)
        self.assertNotIn('input(', s)

    def test_nginx_no_raw_output_and_stage_detection(self):
        raw = (b"server_name staging.kmjtechno.com;\n"
               b"root /home/kmjstage/htdocs/staging.kmjtechno.com/public;\n"
               b"set $private_password value123;")
        got = m.nginx_classify(raw)
        self.assertEqual(got["STAGING_NGINX_HOST"], "ONE_OR_MORE_MATCHES")
        self.assertEqual(got["STAGING_NGINX_STAGE_HOME_HINT"], "REFERENCED")
        self.assertEqual(got["STAGING_NGINX_ROOT_ANCHOR_HINT"], "NOT_SEEN")
        self.assertNotIn("value123", str(got))
        self.assertEqual(m.nginx_classify(None)["STAGING_NGINX_CONFIG"], "UNVERIFIED")

    def test_no_false_vhost_for_similar_name(self):
        got = m.nginx_classify(b"server_name staging.kmjtechno.com.attacker.tld;")
        self.assertEqual(got["STAGING_NGINX_HOST"], "NOT_SEEN")

    def test_pointer_drift(self):
        with tempfile.TemporaryDirectory() as path:
            p = pathlib.Path(path) / "live"
            self.assertEqual(m.link_expected(p, {"good"}), "UNVERIFIED")
            p.symlink_to("good")
            self.assertEqual(m.link_expected(p, {"good"}), "EXPECTED")
            self.assertEqual(m.link_expected(p, {"different"}), "DRIFT")
            p.unlink()
            p.mkdir()
            self.assertEqual(m.link_expected(p, {"good"}), "UNTRUSTED_NOT_SYMLINK")

    def test_reject_root_probe_from_other_host_or_user(self):
        with patch.object(m.os, "geteuid", return_value=1234), \
             patch.object(m, "run_fixed", side_effect=AssertionError("must not execute")):
            self.assertEqual(m.main(), 2)
        with patch.object(m.os, "geteuid", return_value=0), \
             patch.object(m.socket, "gethostname", return_value="other-host"), \
             patch.object(m, "run_fixed", side_effect=AssertionError("must not execute")):
            self.assertEqual(m.main(), 2)

    def test_protected_exec_rejects_malformed_paths(self):
        for x in (None, "foo", "path=../../bad", "path=/good path=/bad",
                  "path=/../../etc/shadow"):
            self.assertEqual(m.protected_exec_reference(x), "NOT_ATTESTED")

    def test_only_fixed_subprocess_probes(self):
        s = SOURCE.read_text()
        self.assertIn('["/usr/sbin/nginx", "-T", "-q"]', s)
        self.assertIn('["/usr/bin/systemctl", "show", BACKUP_UNIT', s)
        self.assertIn('max_bytes=MAX_NGINX_BYTES', s)
        self.assertIn('timeout=15', s)
        self.assertIn('LEGACY_OFFSITE_EXEC_REFERENCE', s)
        self.assertNotIn('journalctl', s)
        self.assertNotIn('ssh ', s)


if __name__ == "__main__":
    unittest.main()
