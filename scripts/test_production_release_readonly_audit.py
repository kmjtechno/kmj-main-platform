"""Offline unit and source-safety contracts for the KMJ release audit."""
from pathlib import Path
import ast
import hashlib
import json
import os
import runpy
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parent / "operations/audit-production-release-blockers-readonly.py"
MODULE = runpy.run_path(str(SCRIPT))


class ProductionReleaseReadOnlyAuditTest(unittest.TestCase):
    def test_operator_needs_explicit_exact_sha_and_never_probes_on_invalid_args(self):
        for args in ([], ["--inspect", "a" * 39], ["--inspect", "oops"]):
            result = subprocess.run(
                [sys.executable, str(SCRIPT), *args],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("BLOCKED_EXACT_SHA_ARGUMENT", result.stdout)

    def test_unprivileged_or_unapproved_host_is_rejected_without_touching_vps(self):
        if os.geteuid() == 0 and os.uname().nodename.split(".")[0] == "KMJ-elite":
            self.skipTest("Never run this test with a valid SHA on production")
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--inspect", "a" * 40],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("BLOCKED_KMJ_ELITE_ROOT_REQUIRED", result.stdout)

    def test_exact_approval_does_not_equal_independently_verified_recovery(self):
        sha = "a" * 40
        current = "platform-8070dad72c55"
        approval = dict(
            approvedSha=sha, expectedCurrentRelease=current,
            backupVerified=True, rollbackVerified=True,
        )
        check = MODULE["check_approval"]
        self.assertEqual(
            check(approval, sha, current),
            "FIELDS_MATCH_FLAGS_NOT_INDEPENDENT_PROOF",
        )
        self.assertEqual(
            check({**approval, "expectedCurrentRelease": "platform-54142f844c0b"}, sha, current),
            "PROTECTED_EXPECTED_CURRENT_RELEASE_MISMATCH",
        )
        self.assertEqual(
            check({**approval, "approvedSha": "b" * 40}, sha, current),
            "APPROVED_CANDIDATE_SHA_MISMATCH",
        )
        self.assertEqual(check({**approval, "backupVerified": False}, sha, current), "UNATTESTED_FLAGS")
        self.assertEqual(check({**approval, "unexpected": 1}, sha, current), "INVALID")
        self.assertEqual(check("unsafe", sha, current), "INVALID")

    def test_backup_witness_requires_current_release_and_exact_sha256(self):
        sha = "c" * 40
        current = "platform-8070dad72c55"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test-backup.tar.gz"
            path.write_bytes(b"fixed-isolated-fixture-not-customer-data")
            witness = {
                "approvedSha": sha, "currentRelease": current,
                "backupSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            check = MODULE["witness_matches"]
            self.assertTrue(check(witness, sha, current, path))
            self.assertFalse(check({**witness, "approvedSha": "d" * 40}, sha, current, path))
            self.assertFalse(check({**witness, "currentRelease": "platform-54142f844c0b"}, sha, current, path))
            self.assertFalse(check({**witness, "backupSha256": "0" * 64}, sha, current, path))
            self.assertFalse(check({**witness, "secret": "x"}, sha, current, path))
            path.write_bytes(b"tampered")
            self.assertFalse(check(witness, sha, current, path))

    def test_source_only_runs_bounded_fixed_read_commands_no_mutations(self):
        source = SCRIPT.read_text()
        tree = ast.parse(source)
        self.assertTrue(tree)
        for token in (
            "KMJ_RELEASE_AUDIT_STAGING=OWNED_BY_SEPARATE_CHAT_NO_ACTION",
            "KMJ_RELEASE_AUDIT_P520_P720=INTENTIONALLY_OFFLINE_NO_ACTION",
        ):
            # Status key and value are separately authored, not string literals joined.
            key, value = token.removeprefix("KMJ_RELEASE_AUDIT_").split("=", 1)
            self.assertIn('report("' + key + '", "' + value + '")', source)
        self.assertIn('report("PRODUCTION_ACTIVATION", "NOT_ATTEMPTED")', source)
        self.assertIn("CURRENT.resolve(strict=True)", source)
        self.assertIn("runuser", source)
        self.assertIn('"GIT_OPTIONAL_LOCKS": "0"', source)
        self.assertIn("witness_matches", source)
        self.assertIn("stat.S_ISREG", source)
        for forbidden in (
            "os.replace(", "os.unlink(", "shutil.rmtree(",
            "subprocess.Popen(", "os.system(", "shell=True",
            "systemctl restart", "systemctl reload", "ln -sfn",
            "artisan migrate", "git reset --hard", "git clean -fd",
            "codebridge-agent restart", "staging.kmjtechno.com",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
