"""Root release-lock hardening: no `exec 9>` through a world-plantable path; behaviour proven on the real snippet."""
import os, re, subprocess, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "scripts/operations"
FILES = ["prepare-main-platform-local-recovery-exact.sh", "materialize-main-platform-candidate-runtime.sh"]


def snippet(text):
    m = re.search(r"readonly RELEASE_LOCK=.*?exec 9<\"\$RELEASE_LOCK\"\n", text, re.S)
    assert m, "hardened lock snippet missing"
    return m.group(0)


class RootLockTests(unittest.TestCase):
    def test_sources_use_safe_lock(self):
        for name in FILES:
            text = (ROOT / name).read_text()
            self.assertNotRegex(text, r"exec 9>/run/lock")
            self.assertIn("set -o noclobber", text)
            self.assertIn("RELEASE_LOCK_UNSAFE", text)
            subprocess.run(["bash", "-n", str(ROOT / name)], check=True)

    def test_no_operations_script_opens_a_lock_with_truncating_redirect(self):
        offenders = [f.name for f in sorted(ROOT.glob("*.sh")) if re.search(r"^\s*exec 9>", f.read_text(), re.M)]
        self.assertEqual(offenders, [])

    def run_snippet(self, lock, uid_ok=True):
        # Swap the fixed path for a temp one; "0:1" owner check is replaced by current uid so it runs unprivileged.
        text = snippet((ROOT / FILES[0]).read_text()).replace("/run/lock/kmj-main-platform-production-release.lock", str(lock))
        text = text.replace('== "0:1"', '== "%d:1"' % (os.getuid() if uid_ok else 0))
        script = 'fail() { echo "BLOCKED $1"; exit 2; }\n' + text + 'echo LOCKED\n'
        return subprocess.run(["bash", "-c", script], capture_output=True, text=True)

    def test_symlink_is_never_followed_or_truncated(self):
        with tempfile.TemporaryDirectory() as d:
            victim = Path(d) / "victim"; victim.write_text("precious")
            lock = Path(d) / "lock"; lock.symlink_to(victim)
            r = self.run_snippet(lock)
            self.assertEqual(r.returncode, 2); self.assertIn("RELEASE_LOCK_UNSAFE", r.stdout)
            self.assertEqual(victim.read_text(), "precious")

    def test_foreign_owner_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            lock = Path(d) / "lock"; lock.write_text("")
            r = self.run_snippet(lock, uid_ok=False)  # file owned by us, expected owner 0
            if os.getuid() != 0:
                self.assertEqual(r.returncode, 2)

    def test_creates_and_reuses_regular_lock(self):
        with tempfile.TemporaryDirectory() as d:
            lock = Path(d) / "lock"
            for _ in range(2):
                r = self.run_snippet(lock)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr); self.assertIn("LOCKED", r.stdout)
            self.assertEqual(oct(lock.stat().st_mode & 0o777), "0o600")


if __name__ == "__main__":
    unittest.main()
