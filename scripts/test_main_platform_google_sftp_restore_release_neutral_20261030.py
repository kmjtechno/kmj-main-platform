#!/usr/bin/env python3
"""Release-neutral Google SFTP restore script: argument validation, metadata binding, no pins. No live access."""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "operations/verify-main-platform-google-sftp-restore-20261030.sh"
SOURCE = SCRIPT.read_text(encoding="utf-8")
META = re.search(r"python3 - \"\$tmp/extracted/metadata.txt\" \"\$expected_source_sha\" \"\$candidate_sha\" \"\$expected_release\" <<'PY'\n(.*?)\nPY\n", SOURCE, re.S).group(1)
SHA = "a" * 40
REL = "platform-" + "b" * 12
SRC = "c" * 64


def run(*args: str, env=None):
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, env=env or dict(os.environ))


def meta(lines: list[str], sha=SHA, rel=REL, src=SRC) -> int:
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "metadata.txt"
        p.write_text("\n".join(lines) + "\n", encoding="ascii")
        return subprocess.run(["python3", "-c", META, str(p), src, sha, rel]).returncode


GOOD = [
    "backup_kind=offsite_sanitized_local_witness",
    f"source_local_sha256={SRC}",
    f"target_sha={SHA}",
    f"current_release={REL}",
    "production_env_excluded=YES",
]


class ReleaseNeutralRestore(unittest.TestCase):
    def test_syntax_and_no_pinned_release(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
        for pinned in ("39b88b36d071", "574e443a2c75", "bbf95ca55df0b031"):
            self.assertNotIn(pinned, SOURCE)

    def test_arguments_are_validated_before_any_host_or_filesystem_check(self):
        bad = [
            (), ("--candidate-sha", SHA), (SHA, REL), ("--expected-release", REL, "--candidate-sha", SHA),
            ("--candidate-sha", SHA, "--expected-release", REL, "extra"),
        ]
        for args in bad:
            r = run(*args)
            self.assertEqual(r.returncode, 2, args)
            self.assertIn("USAGE_CANDIDATE_SHA_AND_EXPECTED_RELEASE_ONLY=BLOCKED", r.stdout)
        for sha in (SHA.upper(), SHA[:-1], SHA + "0", "../" + SHA[:37], SHA[:39] + "g", SHA[:39] + "\n", ""):
            r = run("--candidate-sha", sha, "--expected-release", REL)
            self.assertEqual(r.returncode, 2, sha)
            self.assertIn("CANDIDATE_SHA_INVALID=BLOCKED", r.stdout)
        for rel in ("platform-" + "b" * 11, "platform-" + "B" * 12, "../platform-" + "b" * 12, "release-" + "b" * 12, "platform-" + "b" * 12 + "/x", ""):
            r = run("--candidate-sha", SHA, "--expected-release", rel)
            self.assertEqual(r.returncode, 2, rel)
            self.assertIn("EXPECTED_RELEASE_INVALID=BLOCKED", r.stdout)

    def test_valid_arguments_pass_validation_and_stop_at_operator_gate(self):
        r = run("--candidate-sha", SHA, "--expected-release", REL)
        self.assertEqual(r.returncode, 2)
        self.assertRegex(r.stdout, r"NONROOT_INFO_REQUIRED=BLOCKED|GOOGLE_RECOVERY_HOST_REQUIRED=BLOCKED")

    def test_metadata_binding_accepts_only_the_exact_candidate(self):
        self.assertEqual(meta(GOOD), 0)
        self.assertNotEqual(meta(GOOD, sha="d" * 40), 0)  # old/other candidate
        self.assertNotEqual(meta(GOOD, rel="platform-" + "e" * 12), 0)  # other active release
        self.assertNotEqual(meta(GOOD, src="f" * 64), 0)  # other source archive digest
        self.assertNotEqual(meta(GOOD + ["extra=1"]), 0)
        self.assertNotEqual(meta(GOOD + [GOOD[0]]), 0)  # duplicate key
        self.assertNotEqual(meta([l for l in GOOD if "env_excluded" not in l]), 0)
        self.assertNotEqual(meta([l.replace("=YES", "=NO") for l in GOOD]), 0)
        self.assertNotEqual(meta(GOOD[:-1] + ["garbage-without-equals"]), 0)

    def test_expected_hashes_come_from_validated_environment_only(self):
        self.assertIn('[[ "$expected_source_sha" =~ ^[0-9a-f]{64}$ ]] || block EXPECTED_SOURCE_LOCAL_SHA256', SOURCE)
        self.assertIn("KMJ_EXPECTED_ENCRYPTED_SHA256", SOURCE)
        self.assertIn('encrypted="$HOME/kmj-recovery-scratch/offsite-$short_sha.tar.gz.age"', SOURCE)

    def test_safety_properties_kept(self):
        for needle in ("bwrap", "NONROOT_INFO_REQUIRED", "OPERATOR_CONSENT", "PRODUCTION_DATABASE_MODIFIED NO",
                       "status OFFSITE_RCLONE_RETRIEVAL NOT_ATTEMPTED", "SAFE_TO_ACTIVATE_PRODUCTION NOT_PROVEN",
                       'RESTORE_CANDIDATE_SHA "$candidate_sha"'):
            self.assertIn(needle, SOURCE)
        for prohibited in ("systemctl restart", "artisan migrate", "rclone copy", "ln -sfn"):
            self.assertNotIn(prohibited, SOURCE)


if __name__ == "__main__":
    unittest.main()
