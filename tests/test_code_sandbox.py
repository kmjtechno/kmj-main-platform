import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from controller.code_sandbox import execute_code_candidate


class CodeSandboxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.tests = self.root / "trusted-tests"
        self.tests.mkdir()
        target = self.repo / "apps/platform/tools"
        target.mkdir(parents=True)
        self.path = "apps/platform/tools/calc.py"
        (self.repo / self.path).write_text(
            "import sys\na=int(sys.argv[1]); b=int(sys.argv[2])\nprint(a-b)\n"
        )
        self.git("init", "-q")
        self.git("add", ".")
        self.git(
            "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
            "commit", "-qm", "fixture",
        )
        self.sha = self.git("rev-parse", "HEAD").strip()
        self.diff = (
            f"diff --git a/{self.path} b/{self.path}\n"
            f"--- a/{self.path}\n"
            f"+++ b/{self.path}\n"
            "@@ -1,3 +1,3 @@\n"
            " import sys\n"
            " a=int(sys.argv[1]); b=int(sys.argv[2])\n"
            "-print(a-b)\n"
            "+print(a+b)\n"
        )
        self.write_cases([
            {"args": ["2", "3"], "stdin": "", "exit_code": 0, "stdout": "5\n"},
            {"args": ["-2", "3"], "stdin": "", "exit_code": 0, "stdout": "1\n"},
        ])

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], text=True)

    def write_cases(self, cases, entrypoint=None):
        payload = {
            "schema_version": 1,
            "executor": "python-cli-v1",
            "entrypoint": entrypoint or self.path,
            "cases": cases,
        }
        raw = (json.dumps(payload, sort_keys=True) + "\n").encode()
        (self.tests / "cases.json").write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()

    def execute(self, **kwargs):
        kwargs.setdefault(
            "expected_validation_sha256",
            hashlib.sha256((self.tests / "cases.json").read_bytes()).hexdigest(),
        )
        return execute_code_candidate(
            self.repo,
            self.sha,
            self.diff,
            self.root / "candidates",
            trusted_tests=self.tests,
            allowed_paths=[self.path],
            **kwargs,
        )

    @unittest.skipUnless(shutil.which("bwrap"), "bubblewrap required")
    def test_real_small_code_fix_passes_external_assertions(self):
        digest = hashlib.sha256((self.tests / "cases.json").read_bytes()).hexdigest()
        result = self.execute(expected_validation_sha256=digest)
        self.assertEqual(result["stage"], "code_candidate_tested")
        self.assertEqual(result["tests_run"], 2)
        self.assertEqual(result["tests_passed"], 2)
        self.assertFalse(result["product_complete"])
        self.assertFalse(result["deployed"])
        self.assertTrue(result["candidate_unchanged_during_validation"])
        self.assertEqual(result["validation_sha256"], digest)
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertEqual(self.git("rev-parse", "HEAD").strip(), self.sha)
        self.assertIn("print(a-b)", (self.repo / self.path).read_text())
        self.assertIn("print(a+b)", (Path(result["candidate"]) / self.path).read_text())

    @unittest.skipUnless(shutil.which("bwrap"), "bubblewrap required")
    def test_candidate_cannot_forge_parent_assertion_with_success_text(self):
        self.diff = self.diff.replace("+print(a+b)", '+print("KMJ_VALIDATION_FINISHED:999")')
        result = self.execute()
        self.assertEqual(result["stage"], "tests_failed")
        self.assertEqual(result["tests_passed"], 0)

    @unittest.skipUnless(shutil.which("bwrap"), "bubblewrap required")
    def test_sandbox_has_no_host_secret_network_or_workspace_write(self):
        secret = self.root / "host-secret"
        secret.write_text("hidden")
        source = (
            "import os, pathlib, socket\n"
            f"host=pathlib.Path({str(secret)!r}).exists()\n"
            "env=os.environ.get('KMJ_TEST_SECRET','')\n"
            "try:\n"
            " s=socket.socket(); s.settimeout(.1); s.connect(('1.1.1.1',443)); net='open'\n"
            "except OSError: net='blocked'\n"
            "try:\n"
            " pathlib.Path(__file__).write_text('changed'); write='writable'\n"
            "except OSError: write='readonly'\n"
            "print(f'{host}|{env}|{net}|{write}')\n"
        )
        old = (self.repo / self.path).read_text()
        self.diff = (
            f"diff --git a/{self.path} b/{self.path}\n"
            f"--- a/{self.path}\n+++ b/{self.path}\n"
            f"@@ -1,3 +1,{len(source.splitlines())} @@\n"
            + "".join("-" + line + "\n" for line in old.splitlines())
            + "".join("+" + line + "\n" for line in source.splitlines())
        )
        self.write_cases([
            {"args": [], "stdin": "", "exit_code": 0, "stdout": "False||blocked|readonly\n"}
        ])
        prior = os.environ.get("KMJ_TEST_SECRET")
        os.environ["KMJ_TEST_SECRET"] = "must-not-cross"
        try:
            result = self.execute()
        finally:
            if prior is None:
                os.environ.pop("KMJ_TEST_SECRET", None)
            else:
                os.environ["KMJ_TEST_SECRET"] = prior
        self.assertEqual(result["stage"], "code_candidate_tested")

    def test_patch_scope_must_exactly_match_operator_allowlist(self):
        with self.assertRaisesRegex(ValueError, "PATCH_SCOPE_MISMATCH"):
            execute_code_candidate(
                self.repo, self.sha, self.diff, self.root / "candidates",
                trusted_tests=self.tests,
                allowed_paths=[self.path, "apps/platform/tools/other.py"],
                expected_validation_sha256=hashlib.sha256((self.tests / "cases.json").read_bytes()).hexdigest(),
            )

    def test_global_denied_path_stays_denied(self):
        bad = self.diff.replace(self.path, ".github/workflows/evil.py")
        with self.assertRaises(ValueError):
            execute_code_candidate(
                self.repo, self.sha, bad, self.root / "candidates",
                trusted_tests=self.tests,
                allowed_paths=[".github/workflows/evil.py"],
                expected_validation_sha256=hashlib.sha256((self.tests / "cases.json").read_bytes()).hexdigest(),
            )

    def test_validation_digest_is_pinned(self):
        with self.assertRaisesRegex(ValueError, "VALIDATION_DIGEST_MISMATCH"):
            self.execute(expected_validation_sha256="0" * 64)

    def test_validation_tree_cannot_smuggle_executable_test_code(self):
        (self.tests / "test_evil.py").write_text("raise SystemExit(0)\n")
        with self.assertRaisesRegex(ValueError, "VALIDATION_TREE_MUST_ONLY"):
            self.execute()

    def test_entrypoint_must_be_operator_allowed(self):
        self.write_cases(
            [{"args": [], "stdin": "", "exit_code": 0, "stdout": ""}],
            entrypoint="apps/platform/tools/other.py",
        )
        with self.assertRaisesRegex(ValueError, "ENTRYPOINT_NOT_ALLOWED"):
            self.execute()

    def test_nonempty_stdin_is_not_silently_supported(self):
        self.write_cases([
            {"args": [], "stdin": "secret", "exit_code": 0, "stdout": ""}
        ])
        with self.assertRaisesRegex(ValueError, "VALIDATION_STDIN_UNSUPPORTED"):
            self.execute()

    def test_moved_base_is_rejected(self):
        (self.repo / "apps/platform/tools/other.py").write_text("print('new')\n")
        self.git("add", ".")
        self.git(
            "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
            "commit", "-qm", "move base",
        )
        with self.assertRaisesRegex(ValueError, "BASE_MOVED"):
            self.execute()

    def test_project_lock_rejects_simultaneous_writer(self):
        lock_path = self.repo / ".git/kmj-code-sandbox.lock"
        with lock_path.open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            with self.assertRaisesRegex(ValueError, "PROJECT_BUSY"):
                self.execute()


if __name__ == "__main__":
    unittest.main()
