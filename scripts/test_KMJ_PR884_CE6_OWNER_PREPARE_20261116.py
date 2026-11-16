"""Fail-closed source-only QA for the B5E AI candidate preparation operator.

Runs no production database, backups, Git commands, external SFTP, or service.
"""
from pathlib import Path
import re
import subprocess
import unittest

SRC = Path(__file__).with_name("KMJ_PR884_CE6_OWNER_PREPARE_20261116.sh")
TARGET = "45f95dbf7a4bad29852ab6f45c54873ab39e5a2e"
BASE = "ce6ad7dc9d898dce1ba9561a0e221f8ad750180f"
ONEPASS = "0070697927babaa9a9035ebadcffe9a07311c12bcc4fbbd7a5a9d024cbc00dd3"


class OwnerPrepareContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SRC.read_text(encoding="utf-8")

    def test_syntax_is_valid(self):
        result = subprocess.run(["bash", "-n", str(SRC)], capture_output=True, timeout=10, check=False)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))

    def test_exact_immutable_candidate_and_real_predecessor(self):
        self.assertIn("readonly TARGET_SHA=" + TARGET, self.source)
        self.assertIn("readonly PREVIOUS_SHA=" + BASE, self.source)
        self.assertIn("readonly PREVIOUS_RELEASE=platform-ce6ad7dc9d89", self.source)
        self.assertIn("readonly TARGET_RELEASE=platform-45f95dbf7a4b", self.source)
        self.assertNotIn("platform-e5b43872bc03", self.source)

    def test_no_unreviewed_command_or_arbitrary_sha(self):
        self.assertIn('[[ "$#" -eq 1 && ( "$1" == --inspect || "$1" == --prepare ) ]]', self.source)
        self.assertIn("readonly ONEPASS_SHA256=" + ONEPASS, self.source)
        self.assertIn('[[ "$source_sha" == "$TARGET_SHA" ]]', self.source)
        self.assertIn('[[ "$live_sha" == "$PREVIOUS_SHA" ]]', self.source)
        self.assertIn('"/bin/bash -p" "$scratch/pinned-onepass.sh"', self.source.replace("/bin/bash -p", '"/bin/bash -p"')) 
        for token in ("git reset", "git clean", "git push --force", "curl -k",
                      "rm -rf", "source $", "eval ", "--force-with-lease"):
            self.assertNotIn(token, self.source)

    def test_does_not_approve_activate_or_mutate_production(self):
        for needle in ("systemctl start", "systemctl reload", "main-platform-production-release.json",
                       "os.replace(", "ln -s", "mv -f", "approvalVerified", "rollbackVerified\": True"):
            self.assertNotIn(needle, self.source)
        for needle in ("PROTECTED_APPROVAL UNCHANGED", "PRODUCTION_ACTIVATION NOT_ATTEMPTED",
                       "GOOGLE_INDEPENDENT_RESTORE NOT_VERIFIED",
                       "PHYSICAL_ROLLBACK_DRILL NOT_VERIFIED"):
            self.assertIn(needle, self.source)

    def test_preparation_requires_previous_live_and_no_partial_overwrite(self):
        for needle in ("LIVE_PREDECESSOR_MISMATCH", "LIVE_SHA_MISMATCH",
                       "EXISTING_CANDIDATE_REQUIRES_REVIEW",
                       "EXISTING_BACKUP_REQUIRES_REVIEW",
                       "CANDIDATE_NOT_CHECKED_OUT_AT_EXACT_HEAD",
                       "PRIVATE_COPY_SHA", "CANDIDATE_OUTPUT_SHA"):
            self.assertIn(needle, self.source)

    def test_backup_proof_rejects_symlink_dup_keys_and_wrong_binding(self):
        for needle in ("os.O_NOFOLLOW", "witness_metadata", "duplicate_key",
                       'record["approvedSha"] != target',
                       'record["currentRelease"] != previous',
                       'checked(archive, 20 * 1024 ** 3) != record["backupSha256"]'):
            self.assertIn(needle, self.source)

    def test_rejects_invalid_args_before_root_check(self):
        result = subprocess.run(["bash", "-p", str(SRC), "--finish"],
                                capture_output=True, timeout=10, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"BLOCKED_EXACT_MODE", result.stdout)
        result = subprocess.run(["bash", "-p", str(SRC)],
                                capture_output=True, timeout=10, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"BLOCKED_EXACT_MODE", result.stdout)


if __name__ == "__main__":
    unittest.main()
