"""No-cutover recovery script accepts only exact main and exact current release."""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "scripts/operations/prepare-current-main-production-recovery-20261027.sh"


class CurrentMainRecoveryContract(unittest.TestCase):
    def test_bash_parse(self):
        subprocess.run(["bash", "-n", str(FILE)], check=True, timeout=10)

    def test_exact_arguments_only(self):
        for args in ([], ["main"], ["a" * 40], ["a" * 40, "not_release"]):
            with self.subTest(args=args):
                r = subprocess.run(["bash", str(FILE), *args], capture_output=True, text=True, timeout=8)
                self.assertEqual(r.returncode, 2)
                self.assertIn("KMJ_LOCAL_RECOVERY=BLOCKED", r.stdout)

    def test_other_host_does_not_start_backup(self):
        r = subprocess.run(
            ["bash", str(FILE), "a" * 40, "platform-8070dad72c55"],
            capture_output=True, text=True, timeout=8,
        )
        self.assertEqual(r.returncode, 2)
        self.assertIn("WRONG_HOST", r.stdout)

    def test_exact_sha_and_current_link_gates(self):
        s = FILE.read_text(encoding="utf-8")
        for term in (
            'readonly TARGET_SHA="$1"', 'readonly EXPECTED_CURRENT_RELEASE="$2"',
            "MAIN_REMOTE_UNAVAILABLE", "TARGET_NOT_CURRENT_MAIN",
            "CURRENT_SOURCE_MISMATCH", "CURRENT_RELEASE_CHANGED",
            "TARGET_ALREADY_LIVE", "CANDIDATE_ARTIFACT_MISSING",
            "STORAGE_APP_HAS_LINKS", "REMOTE_MAIN_MOVED",
            "CURRENT_RELEASE_MOVED",
            "LOCAL_DISPOSABLE_POSTGRES_RESTORE", "LOCAL_BACKUP_WITNESS",
            "OFFSITE_INDEPENDENT_RESTORE", "NOT_VERIFIED",
            "ROLLBACK_DRILL", "NOT_VERIFIED",
            "PRODUCTION_SWITCH", "NOT_ATTEMPTED",
            "APPROVAL_UPDATED", "NO",
            "/var/backups/kmj-platform",
        ):
            with self.subTest(term=term):
                self.assertIn(term, s)

    def test_release_lock_is_nofollow_and_nontruncating(self):
        """Execute the actual lock snippet with a disposable unprivileged path."""
        import os
        import re
        import tempfile

        source = FILE.read_text(encoding="utf-8")
        self.assertNotIn("exec 9>", source)
        self.assertIn("set -o noclobber", source)
        self.assertIn('stat -c \'%u:%h\'', source)
        self.assertIn("/proc/self/fd/9", source)
        self.assertIn("RELEASE_LOCK_FD_MISMATCH", source)
        self.assertNotIn("chmod 0600 -- \"$RELEASE_LOCK\"", source)
        match = re.search(
            r"(?ms)^readonly RELEASE_LOCK=.*?^flock -n 9[^\n]*$", source
        )
        self.assertIsNotNone(match)
        snippet = match.group(0)
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            lock = directory / "release.lock"
            victim = directory / "victim"
            victim.write_text("PRESERVE_ME", encoding="utf-8")
            local = snippet.replace(
                "/run/lock/kmj-main-platform-production-release.lock",
                str(lock),
            ).replace('"0:1"', f'"{os.getuid()}:1"')
            command = "set -Eeuo pipefail\nfail() { exit 2; }\n" + local
            # Existing symlink must be refused without touching its target.
            lock.symlink_to(victim)
            blocked = subprocess.run(["bash", "-c", command], capture_output=True, timeout=8)
            self.assertEqual(blocked.returncode, 2)
            self.assertEqual(victim.read_text(encoding="utf-8"), "PRESERVE_ME")
            lock.unlink()
            # A second hard link must also be refused before chmod/open.
            os.link(victim, lock)
            blocked = subprocess.run(["bash", "-c", command], capture_output=True, timeout=8)
            self.assertEqual(blocked.returncode, 2)
            self.assertEqual(victim.read_text(encoding="utf-8"), "PRESERVE_ME")
            lock.unlink()
            # A root-owned but incorrectly permissive existing lock must not be
            # silently chmod'ed (nor have its bytes overwritten).
            lock.write_text("KEEP_MODE_AND_BYTES", encoding="utf-8")
            lock.chmod(0o644)
            blocked = subprocess.run(["bash", "-c", command], capture_output=True, timeout=8)
            self.assertEqual(blocked.returncode, 2)
            self.assertEqual(lock.read_text(encoding="utf-8"), "KEEP_MODE_AND_BYTES")
            self.assertEqual(lock.stat().st_mode & 0o777, 0o644)
            lock.unlink()
            # A clean private lock is created and can be reopened safely.
            for _ in range(2):
                allowed = subprocess.run(["bash", "-c", command], capture_output=True, timeout=8)
                self.assertEqual(allowed.returncode, 0, allowed.stderr)
                self.assertEqual(lock.stat().st_mode & 0o777, 0o600)

    def test_no_production_writes_or_fake_approval(self):
        s = FILE.read_text(encoding="utf-8")
        for forbidden in (
            "systemctl restart", "systemctl reload", "artisan migrate",
            "ALTER ROLE", "DROP DATABASE", "git reset", "git clean",
            "ln -s", "os.replace", "backupVerified=True",
            "rollbackVerified=True", "/etc/kmj-codebridge/main-platform-production-release.json",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, s)


if __name__ == "__main__":
    unittest.main()
