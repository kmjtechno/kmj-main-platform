"""Offline trust-boundary checks for candidate rollback's root-only integration.

The protected materializer remains a Draft; source-level checks never confer
approval to execute it on KMJ-elite or certify a production rollback.
"""
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/operations/materialize-main-platform-candidate-runtime.sh"
LIBRARY = ROOT / "scripts/operations/protected-candidate-retire-20261103.py"


class RootRetireIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SCRIPT.read_text()
        cls.library = LIBRARY.read_text()

    def test_no_old_writable_directory_quarantine_unlink(self):
        s = self.source
        self.assertNotIn("os.unlink(q, dir_fd=dir_fd)", s)
        self.assertNotIn("restore_or_quarantine(dir_fd, name, q)", s)
        self.assertNotIn("os.rename(name, q,", s)
        self.assertIn('return "QUARANTINED"', s)
        self.assertIn('status CANDIDATE_ROLLBACK FAILED_REVIEW', s)

    def test_root_helper_embedded_and_never_imported_from_candidate(self):
        s = self.source
        self.assertEqual(s.count("KMJ_ROOT_PROTECTED_RETIRE_PY"), 2)
        marker = "<<'KMJ_ROOT_PROTECTED_RETIRE_PY'\n"
        self.assertIn(marker, s)
        embedded = s.split(marker, 1)[1].split("\nKMJ_ROOT_PROTECTED_RETIRE_PY", 1)[0]
        compile(embedded, "<approved-root-wrapper-retirement>", "exec")
        self.assertIn("def retire_created(", embedded)
        self.assertIn("def _validated_quarantine(", embedded)
        self.assertIn("if os.geteuid()", embedded.replace("len(argv) != 5 or ", ""))
        self.assertIn("PRIVATE_QUARANTINE_NOT_TRUSTED", embedded)
        self.assertIn("QUARANTINE_ANCESTOR_UNSAFE", embedded)
        self.assertIn("KMJ_ROOT_PROTECTED_RETIRE_PY", s)
        self.assertLess(s.index("KMJ_UNPRIVILEGED_MATERIALIZE\n"),
                        s.index("root_retire() {"))
        self.assertNotIn("importlib", embedded)

    def test_root_retire_called_only_from_root_wrapper(self):
        source = self.source
        begin = source.index("IFS= read -r -d '' SANDBOX_BODY")
        end = source.index("KMJ_UNPRIVILEGED_MATERIALIZE\n", begin)
        sandbox = source[begin:end]
        self.assertNotIn('root_retire ', sandbox)
        root = source[end:]
        self.assertIn('link_state="$(root_retire storage "$link_id")"', root)
        self.assertIn('env_state="$(root_retire env "$env_id")"', root)
        self.assertIn('if [[ "$receipt_invalid" == 0 && "$cleanup_rc" == 0 ]]', root)
        self.assertIn("CANDIDATE_ROLLBACK FAILED_REVIEW", source)
        self.assertNotIn('run_sandbox rollback rollback', root)

    def test_fixed_quarantine_parent_and_no_credential_changes(self):
        s = self.source
        self.assertIn('open_dir("/var/lib", root_protected=True)', s)
        self.assertIn('os.mkdir(label, mode=0o700, dir_fd=parent)', s)
        self.assertIn('os.O_NOFOLLOW', s)
        self.assertIn('q.st_dev != source.st_dev', s)
        self.assertNotIn('systemctl restart', s)
        self.assertNotIn('ssh-keygen', s)
        self.assertNotIn('chmod 777', s)

    def test_bash_parser_and_root_heredoc_syntax(self):
        r = subprocess.run(["bash", "-n", str(SCRIPT)],
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
