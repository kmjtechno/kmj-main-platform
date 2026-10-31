"""Negative tests for the advisory-only stage pointer audit.

No root access, VPS calls, network, database, or staging mutation.
"""
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/operations/audit-isolated-staging-continuity-20261027.sh"


class StageContinuityAuditSafety(unittest.TestCase):
    def test_bash_syntax(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True, timeout=10)

    def test_invalid_sha_rejected_before_host_access(self):
        run = subprocess.run(
            ["bash", str(SCRIPT), "main"],
            capture_output=True, text=True, timeout=8,
        )
        self.assertEqual(run.returncode, 2)
        self.assertIn("KMJ_STAGE_AUDIT=BLOCKED_INVALID_SHA", run.stdout)

    def test_non_kmj_host_rejected(self):
        run = subprocess.run(
            ["bash", str(SCRIPT), "f" * 40],
            capture_output=True, text=True, timeout=8,
        )
        self.assertEqual(run.returncode, 2)
        self.assertIn("KMJ_STAGE_AUDIT=BLOCKED_WRONG_HOST", run.stdout)

    def test_advisory_only_and_never_ready(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for required in (
            "STAGING_IMMUTABLE_OWNER_SEAL=NOT_ATTESTED",
            "STAGING_APPROVED_HEAD_MATCH=NOT_QUERIED",
            "STAGING_SOURCE_HEAD=NOT_ATTESTED",
            "STAGING_ENV_PARITY=NOT_READ",
            "STAGING_DB_SCOPE=NOT_VERIFIED",
            "STAGING_STORAGE_CONTINUITY=NOT_ATTESTED",
            "STAGING_MIGRATION_READBACK=NOT_EXECUTED",
            "OWNER_AUTHENTICATED_QA=NOT_VERIFIED",
            "INDEPENDENT_RESTORE=NOT_VERIFIED",
            "STAGING_READONLY_PRECHECK=BLOCKED_OWNER_SEAL_REQUIRED",
            "exit 2",
        ):
            with self.subTest(required=required):
                self.assertIn(required, source)
        self.assertNotIn("STAGING_READONLY_PRECHECK=PASS", source)

    def test_no_stage_code_or_network_execution(self):
        source = SCRIPT.read_text(encoding="utf-8")
        # Exclude comments: the rationale explicitly names forbidden operations.
        executable = "\n".join(
            line for line in source.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
        for pattern in (
            r"\brunuser\b", r"\bphp(?:8\\.4)?\b", r"\bpython3\b",
            r"\bgit\b", r"\bcurl\b", r"\bwget\b", r"\bssh\b",
            r"\bsudo\b", r"\beval\b", r"\bsource\s+",
            r"\b(systemctl|service|rsync|scp|sftp)\b",
        ):
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, executable, re.IGNORECASE))
        for forbidden in (
            "read_bytes(", "read_text(", "cat .env", "source .env",
            "STAGING_DB_SCOPE=STAGING_ONLY", "STAGING_MIGRATION_READBACK=NO_PENDING_REPORTED",
            "STAGING_ENV_PARITY=PASS",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, executable)

    def test_fixed_paths_and_no_mutations(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for required in (
            "/home/kmjprod/current",
            "/home/kmjstage/htdocs/staging.kmjtechno.com",
            "/home/kmjstage/releases",
            "PRODUCTION_POINTER=OBSERVED_UNCHANGED",
            "STAGING_POINTER=OBSERVED_UNCHANGED",
        ):
            self.assertIn(required, source)
        for forbidden in (
            "git reset", "git clean", "ln -s", "mv -T",
            "systemctl start", "systemctl restart", "artisan migrate",
            "rm -rf", "chmod ", "chown ",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
