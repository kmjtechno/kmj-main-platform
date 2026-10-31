"""Read-only production storage inventory must avoid revealing filenames or mutating releases."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/operations/audit-production-candidate-storage-20261027.py"
SPEC = importlib.util.spec_from_file_location("kmj_production_storage_audit", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class CandidateStorageAudit(unittest.TestCase):
    def test_invalid_args_refused(self):
        run = subprocess.run([sys.executable, "-B", str(SCRIPT), "main"],
                             capture_output=True, text=True, timeout=8)
        self.assertEqual(run.returncode, 2)
        self.assertIn("BLOCKED_EXACT_SHA", run.stdout)

    def test_refuses_non_production_host(self):
        run = subprocess.run([sys.executable, "-B", str(SCRIPT), "a" * 40],
                             capture_output=True, text=True, timeout=8)
        self.assertEqual(run.returncode, 2)
        self.assertIn("BLOCKED_HOST", run.stdout)

    def test_identifies_same_vs_conflict_without_disclosure(self):
        with tempfile.TemporaryDirectory() as temp:
            old_home = module.BASE
            try:
                root = Path(temp)
                module.BASE = root
                original, candidate = root / "original", root / "candidate"
                original.mkdir()
                candidate.mkdir()
                (original / ".gitignore").write_text("ignore me")
                (candidate / ".gitignore").write_text("ignore me")
                a, syma = module.inventory(original)
                b, symb = module.inventory(candidate)
                self.assertEqual(a, b)
                self.assertEqual((syma, symb), (0, 0))
                (candidate / ".gitignore").write_text("changed")
                b, _ = module.inventory(candidate)
                self.assertNotEqual(a, b)
                (candidate / "foreign").symlink_to("/etc", target_is_directory=True)
                _, syms = module.inventory(candidate)
                self.assertEqual(syms, 1)
            finally:
                module.BASE = old_home

    def test_source_cannot_change_live_pointer_or_backup(self):
        code = SCRIPT.read_text()
        for snippet in (
            "git_head(candidate)", "PRODUCTION_POINTER=UNCHANGED",
            "PUBLIC_OLD_FILES", "PRIVATE_OLD_FILES",
            "PUBLIC_CONFLICTS", "PRIVATE_CONFLICTS",
            "NEEDS_GUARDED_PRESERVATION", "os.O_NOFOLLOW",
        ):
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, code)
        for prohibited in (
            "os.replace", "os.symlink", "os.unlink", "os.remove",
            ".write_bytes(", ".write_text(", "rm -rf", "systemctl",
            "artisan migrate", "pg_restore", "git reset",
            "print(relative)", "print(files)",
        ):
            with self.subTest(prohibited=prohibited):
                self.assertNotIn(prohibited, code)


if __name__ == "__main__":
    unittest.main()
