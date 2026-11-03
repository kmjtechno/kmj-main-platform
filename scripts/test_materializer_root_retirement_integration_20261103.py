"""Offline trust-boundary checks for candidate rollback's root-only integration.

The protected materializer remains a Draft; source-level checks never confer
approval to execute it on KMJ-elite or certify a production rollback.
"""
from pathlib import Path
import contextlib
import io
import os
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
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
        self.assertIn('return "BLOCKED_UNPRIVILEGED"', s)
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
        self.assertIn('return 0 if state == "REMOVED" else 3', s)
        self.assertNotIn('systemctl restart', s)
        self.assertNotIn('ssh-keygen', s)
        self.assertNotIn('chmod 777', s)

    def _embedded_root_scope(self):
        marker = "<<'KMJ_ROOT_PROTECTED_RETIRE_PY'\n"
        block = self.source.split(marker, 1)[1].split(
            "\nKMJ_ROOT_PROTECTED_RETIRE_PY", 1)[0]
        entrypoint = "\ntry:\n    raise SystemExit(run(sys.argv))"
        self.assertIn(entrypoint, block)
        scope = {"__name__": "kmj_root_retire_review_tests"}
        exec(compile(block.split(entrypoint, 1)[0],
                     "<embedded-protected-root-retire>", "exec"), scope)
        return scope

    def _run_simulated_root(self, *, swap_foreign: bool):
        # This test executes EXACT embedded production logic with a synthetic
        # pinned root FD mapping. No real /var/lib or /home paths are touched.
        scope = self._embedded_root_scope()
        uid = os.geteuid()
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            candidate = work / "candidate"
            live = work / "live"
            private = work / "root-trusted-parent"
            for p in (candidate, live, private):
                p.mkdir(mode=0o700)
            payload = b"APP_KEY=base64:only-test\nDB=database\n"
            (live / ".env").write_bytes(payload)
            env = candidate / ".env"
            env.write_bytes(payload)
            env.chmod(0o600)
            receipt = f"{env.stat().st_dev}:{env.stat().st_ino}"
            if swap_foreign:
                (candidate / "foreign").write_bytes(b"DO_NOT_DELETE_FOREIGN")
            cp = "/home/kmjprod/releases/platform-aaaaaaaaaaaa/apps/platform"
            lp = "/home/kmjprod/releases/platform-bbbbbbbbbbbb/apps/platform"
            mapping = {cp: candidate, lp: live, "/var/lib": private}

            def fake_open_dir(path, *, root_protected=False):
                # Trust boundaries are asserted statically; here we exercise
                # real rename/check/delete operations with same-fs temp FDs.
                return os.open(mapping[path], os.O_RDONLY | os.O_DIRECTORY)

            original_validator = scope["_validated_quarantine"]

            def simulated_validator(qfd, source_fd, *, trusted_uid=0):
                return original_validator(qfd, source_fd, trusted_uid=uid)

            scope["open_dir"] = fake_open_dir
            scope["_validated_quarantine"] = simulated_validator
            original_rename = os.rename

            def rename_with_attack(src, dst, *, src_dir_fd=None,
                                   dst_dir_fd=None):
                if swap_foreign and src == ".env" and dst == "object":
                    original_rename(candidate / ".env", candidate / "ours")
                    original_rename(candidate / "foreign", candidate / ".env")
                return original_rename(src, dst, src_dir_fd=src_dir_fd,
                                       dst_dir_fd=dst_dir_fd)

            out = io.StringIO()
            with patch.object(os, "geteuid", return_value=0), \
                 patch.object(scope["socket"], "gethostname",
                              return_value="kmj-elite"), \
                 patch.object(scope["pwd"], "getpwnam",
                              return_value=SimpleNamespace(pw_uid=uid)), \
                 patch.object(os, "rename", side_effect=rename_with_attack), \
                 contextlib.redirect_stdout(out):
                outcome = scope["run"](["script", cp, lp, "env", receipt])

            self.assertEqual((live / ".env").read_bytes(), payload)
            if swap_foreign:
                self.assertEqual(outcome, 3)
                self.assertIn("QUARANTINED_OWNER_REVIEW", out.getvalue())
                self.assertEqual((candidate / "ours").read_bytes(), payload)
                tickets = list((private / "kmj-main-platform-rollback-quarantine").iterdir())
                self.assertEqual(len(tickets), 1)
                self.assertEqual((tickets[0] / "object").read_bytes(),
                                 b"DO_NOT_DELETE_FOREIGN")
            else:
                self.assertEqual(outcome, 0, out.getvalue())
                self.assertEqual(out.getvalue().strip(), "REMOVED")
                self.assertFalse(env.exists())
                self.assertEqual(list((private / "kmj-main-platform-rollback-quarantine").iterdir()), [])

    def test_embedded_root_removes_verified_candidate_only(self):
        self._run_simulated_root(swap_foreign=False)

    def test_embedded_root_preserves_foreign_concurrent_swap(self):
        self._run_simulated_root(swap_foreign=True)

    def test_bash_parser_and_root_heredoc_syntax(self):
        r = subprocess.run(["bash", "-n", str(SCRIPT)],
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
