"""Source-only contract for the exact existing dfa55 AGE SFTP owner transfer.

No SSH, archive, root service, production or Google restore is invoked by CI.
"""
from __future__ import annotations

import hashlib
import pathlib
import re
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/operations/push-existing-dfa55-offsite-only-20261102.sh"
UPLOADER = ROOT / "scripts/operations/push-offsite-pinned-sftp-20261030.sh"
EXPECTED_UPLOADER = "c2fbaa2e969ff0fdfcf0ce88b4edb32e3260e59d568ef1411721026a28ef45dc"
EXPECTED_ARCHIVE = "fb333fd5fba4b64a8619e405b914ba171235318f435053e2203d1353407de5cc"


class ExistingDfa55SftpOnlyTests(unittest.TestCase):
    def test_bash_syntax_and_privileged_interpreter(self):
        p = subprocess.run(["/bin/bash", "-n", str(SCRIPT)],
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, 0, p.stderr)
        p = subprocess.run(["/bin/bash", str(SCRIPT)],
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, 2, p.stdout)
        self.assertIn("BLOCKED_PRIVILEGED_BASH_REQUIRED", p.stdout)
        p = subprocess.run(["/bin/bash", "-p", str(SCRIPT), "--unexpected"],
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, 2, p.stdout)
        self.assertIn("BLOCKED_NO_ARGUMENTS", p.stdout)

    def test_immutable_existing_ciphertext_and_production_guard(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for required in (
            "dfa55d24b7cc5a0d1e0b0f28832d1f46acc9d031",
            "offsite-dfa55d24b7cc.tar.gz.age",
            EXPECTED_ARCHIVE,
            "'0:600:1:290397'",
            "platform-574e443a2c75",
            "ARCHIVE_SHA256_MISMATCH",
            "PRODUCTION_POINTER_DRIFT",
            "PRODUCTION_POINTER_CHANGED",
            "GOOGLE_INDEPENDENT_RESTORE=NOT_VERIFIED",
            "PRODUCTION_CHANGED=NO",
        ):
            self.assertIn(required, text)
        self.assertIn('[[ $# -eq 0 ]] || block NO_ARGUMENTS', text)

    def test_pinned_uploader_matches_source_and_strict_ssh(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(hashlib.sha256(UPLOADER.read_bytes()).hexdigest(),
                         EXPECTED_UPLOADER)
        self.assertIn(EXPECTED_UPLOADER, text)
        self.assertIn("68151bcf135991a610ff7eceac25bacf6114b8d9", text)
        self.assertIn('/bin/bash -p "$work/uploader.sh" --candidate-sha "$CANDIDATE"', text)
        uploader = UPLOADER.read_text(encoding="utf-8")
        for guard in ("HOSTKEY_PIN PASS", "REMOTE_COMMIT_NO_CLOBBER PASS",
                      "REMOTE_READBACK_MODE_0600 PASS", "REMOTE_READBACK_SHA256 PASS",
                      "OFFSITE_PUSH PASS", "IdentityAgent=none",
                      "StrictHostKeyChecking=yes"):
            self.assertIn(guard, uploader)

    def test_no_backup_reseal_restore_or_deploy_execution(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(text.count('/bin/bash -p "$work/uploader.sh"'), 1)
        self.assertIsNone(re.search(
            r"(?m)^\s*(?:pg_dump|age|systemctl|git reset|ln -sfn|"
            r"python3.*seal-main-platform|bash.*prepare-full-offsite)\b", text))
        self.assertNotIn("STAGING_ACTIVATION=PASS", text)
        self.assertNotIn("GOOGLE_INDEPENDENT_RESTORE=PASS", text)


if __name__ == "__main__":
    unittest.main()
