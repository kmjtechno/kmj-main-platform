"""Actual transient systemd sandbox smoke test on ephemeral hosted CI only."""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "operations"))
import elite_collect_rollback_rehearsal_receipt as collector


@unittest.skipUnless(os.environ.get("GITHUB_ACTIONS") == "true" and
                     os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted" and
                     os.geteuid() == 0, "ephemeral hosted CI only")
class SandboxIntegration(unittest.TestCase):
    def test_actual_transient_identity_and_file_denial(self):
        with tempfile.TemporaryDirectory(dir="/var/lib") as dirname:
            base = pathlib.Path(dirname)
            base.chmod(0o755)
            fixture = base / "fixture"
            fixture.write_text("readonly")
            fixture.chmod(0o644)
            source = """
import os, pathlib, socket, tempfile
assert os.geteuid() != 0
assert os.environ["DB_PASSWORD"] == "synthetic_ci_only"
p = pathlib.Path(os.environ["TEST_FIXTURE"])
assert p.read_text() == "readonly"
try:
    p.write_text("unexpected")
except PermissionError:
    pass
else:
    raise AssertionError("workspace writable")
try:
    os.listdir("/root")
except PermissionError:
    pass
else:
    raise AssertionError("root home accessible")
with tempfile.TemporaryDirectory() as d:
    pathlib.Path(d, "scratch").write_text("ok")
with socket.socket() as s:
    s.bind(("127.0.0.1", 0))
print("SANDBOX_RUNTIME=PASS")
"""
            runner = base / "runner.py"
            runner.write_text(source)
            runner.chmod(0o500)
            original = collector.REHEARSAL
            try:
                collector.REHEARSAL = runner
                output = collector.run_rehearsal({"TEST_FIXTURE": str(fixture),
                                                  "DB_PASSWORD": "synthetic_ci_only"})
            finally:
                collector.REHEARSAL = original
            self.assertEqual(output.strip(), "SANDBOX_RUNTIME=PASS")
            self.assertEqual(fixture.read_text(), "readonly")


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(SandboxIntegration))
    sys.exit(0 if result.wasSuccessful() and result.testsRun == 1 and not result.skipped else 1)
