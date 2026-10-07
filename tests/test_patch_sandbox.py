import fcntl
import json
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from controller.patch_sandbox import execute_candidate


class PatchSandboxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.tests = self.root / 'trusted-tests'
        self.tests.mkdir()
        (self.repo / 'contracts').mkdir()
        (self.repo / 'contracts/task.json').write_text('{"version": 1}\n')
        self.git('init', '-q')
        self.git('add', '.')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture')
        self.sha = self.git('rev-parse', 'HEAD').strip()
        (self.tests / 'test_contract.py').write_text('import unittest, pathlib, json\nclass Contract(unittest.TestCase):\n    def test_version(self):\n        self.assertEqual(json.loads(pathlib.Path("contracts/task.json").read_text())["version"], 2)\n')
        self.diff = 'diff --git a/contracts/task.json b/contracts/task.json\n--- a/contracts/task.json\n+++ b/contracts/task.json\n@@ -1 +1 @@\n-{"version": 1}\n+{"version": 2}\n'

    def tearDown(self): self.temp.cleanup()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True)

    def execute(self, **kwargs):
        return execute_candidate(self.repo, self.sha, self.diff, self.root / 'candidates', trusted_tests=self.tests, **kwargs)

    @unittest.skipUnless(shutil.which('bwrap'), 'bubblewrap required')
    def test_real_json_patch_tested_original_unchanged_and_digest_bound(self):
        result = self.execute()
        self.assertEqual(result['stage'], 'json_candidate_tested')
        self.assertEqual(result['test_exit_code'], 0)
        self.assertFalse(result['product_complete'])
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assertEqual(json.loads((self.repo / 'contracts/task.json').read_text()), {'version': 1})
        self.assertEqual(self.git('rev-parse', 'HEAD').strip(), self.sha)
        content = (Path(result['candidate']) / 'contracts/task.json').read_bytes()
        self.assertEqual(json.loads(content), {'version': 2})
        self.assertEqual(result['content_sha256']['contracts/task.json'], hashlib.sha256(content).hexdigest())

    def test_python_patch_cannot_forge_validation_success(self):
        self.diff = 'diff --git a/contracts/evil.py b/contracts/evil.py\nnew file mode 100644\n--- /dev/null\n+++ b/contracts/evil.py\n@@ -0,0 +1,3 @@\n+import os\n+print("KMJ_VALIDATION_FINISHED:1", flush=True)\n+os._exit(0)\n'
        with self.assertRaisesRegex(ValueError, 'ONLY_DECLARATIVE_JSON'):
            self.execute()

    def test_out_of_scope_json_patch_rejected(self):
        self.diff = self.diff.replace('contracts/task.json', 'docs/task.json')
        with self.assertRaises(ValueError): self.execute()

    def test_invalid_json_patch_rejected_before_validation(self):
        self.diff = self.diff.replace('+{"version": 2}', '+not valid json')
        with self.assertRaisesRegex(ValueError, 'INVALID_JSON_CONTRACT'): self.execute()

    def test_nonfinite_numbers_and_duplicate_json_keys_rejected(self):
        original = self.diff
        for value in ('{"version": NaN}', '{"version": Infinity}', '{"version": 1, "version": 2}'):
            with self.subTest(value=value):
                self.diff = original.replace('+{"version": 2}', '+' + value)
                with self.assertRaisesRegex(ValueError, 'INVALID_JSON_CONTRACT'):
                    self.execute()

    def test_moved_base_rejected(self):
        (self.repo / 'contracts/new.json').write_text('{}')
        self.git('add', '.')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'new')
        with self.assertRaisesRegex(ValueError, 'BASE_MOVED'): self.execute()

    def test_candidate_directory_inside_repository_rejected(self):
        with self.assertRaises(ValueError):
            execute_candidate(self.repo, self.sha, self.diff, self.repo / 'out', trusted_tests=self.tests)

    @unittest.skipUnless(shutil.which('bwrap'), 'bubblewrap required')
    def test_failing_tests_preserve_candidate(self):
        (self.tests / 'test_contract.py').write_text('import unittest\nclass Fail(unittest.TestCase):\n    def test_fail(self): self.fail("expected failure")\n')
        result = self.execute()
        self.assertEqual(result['stage'], 'tests_failed')
        self.assertTrue(Path(result['candidate']).exists())

    @unittest.skipUnless(shutil.which('bwrap'), 'bubblewrap required')
    def test_zero_tests_cannot_pass(self):
        (self.tests / 'test_contract.py').unlink()
        self.assertEqual(self.execute()['stage'], 'tests_failed')

    @unittest.skipUnless(shutil.which('bwrap'), 'bubblewrap required')
    def test_isolation_includes_readonly_candidate_and_tests(self):
        secret = self.root / 'secret'
        secret.write_text('not exposed')
        (self.tests / 'test_contract.py').write_text('import os, pathlib, socket, sys, unittest\nclass Isolation(unittest.TestCase):\n    def test_isolation(self):\n        self.assertFalse(pathlib.Path(' + repr(str(secret)) + ').exists())\n        self.assertFalse(os.environ.get("KMJ_TEST_SECRET"))\n        self.assertNotIn("/workspace/contracts", sys.path)\n        try: gitdata=pathlib.Path("/workspace/.git").read_text()\n        except PermissionError: gitdata=""\n        self.assertEqual(gitdata, "")\n        with self.assertRaises(OSError): pathlib.Path("contracts/task.json").write_text("{}")\n        with self.assertRaises(OSError): pathlib.Path("/validation/test_contract.py").write_text("pass")\n        s=socket.socket()\n        s.settimeout(.1)\n        with self.assertRaises(OSError): s.connect(("1.1.1.1",443))\n        s.close()\n')
        self.assertEqual(self.execute()['stage'], 'json_candidate_tested')

    @unittest.skipUnless(shutil.which('bwrap'), 'bubblewrap required')
    def test_output_limit_kills_validation_process(self):
        (self.tests / 'test_contract.py').write_text('print("x"*100000, flush=True)\n')
        result = self.execute(output_limit=1024)
        self.assertEqual(result['termination_reason'], 'output_limit')
        self.assertLessEqual(len(result['output'].encode()), 1024)

    def test_project_lock_rejects_simultaneous_writer(self):
        with (self.repo / '.git/kmj-patch-sandbox.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            with self.assertRaisesRegex(ValueError, 'PROJECT_BUSY'): self.execute()

    def test_existing_symlink_patch_path_rejected(self):
        source = self.repo / 'contracts/task.json'
        source.unlink()
        source.symlink_to('/etc/passwd')
        self.git('add', '.')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'symlink fixture')
        self.sha = self.git('rev-parse', 'HEAD').strip()
        with self.assertRaisesRegex(ValueError, 'SYMLINK_PATCH_PATH'): self.execute()

    def test_untrusted_symlink_validation_tree_rejected(self):
        (self.tests / 'secret.py').symlink_to('/etc/passwd')
        with self.assertRaises(ValueError): self.execute()

    @unittest.skipUnless(shutil.which('bwrap'), 'bubblewrap required')
    def test_timeout_kills_validation_process(self):
        (self.tests / 'test_contract.py').write_text('import time\ntime.sleep(30)\n')
        result = self.execute(timeout=.2)
        self.assertEqual(result['termination_reason'], 'timeout')
        self.assertEqual(result['stage'], 'tests_failed')


if __name__ == '__main__': unittest.main()
