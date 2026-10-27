"""Guard read-only isolated staging diagnosis on KMJ-elite."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/operations/inspect-isolated-staging-20261027.sh"
EXPECTED = "b7b39174f5fdf47dd25890ece85c54eef29b4a96"

class IsolatedStageDoctorContract(unittest.TestCase):
    def test_bash_syntax(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], timeout=10, check=True)

    def test_malformed_sha_refused_before_any_remote_inspection(self):
        p = subprocess.run(["bash", str(SCRIPT), "main"], capture_output=True, text=True, timeout=8)
        self.assertEqual(p.returncode, 2)
        self.assertIn("STAGING_DOCTOR=INVALID_SHA", p.stdout)

    def test_non_kmj_host_refused_without_side_effect(self):
        p = subprocess.run(["bash", str(SCRIPT), EXPECTED], capture_output=True, text=True, timeout=8)
        self.assertEqual(p.returncode, 2)
        self.assertIn("STAGING_DOCTOR=WRONG_HOST_OR_USER", p.stdout)

    def test_existing_staging_layout_is_scoped_and_production_safe(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for marker in (
            "/home/kmjstage/htdocs/staging.kmjtechno.com",
            "/home/kmjstage/releases/*/apps/platform",
            "/home/kmjprod/current",
            "PRODUCTION_POINTER=UNCHANGED",
            "STAGING_LOCAL_GIT_SHA=UNAVAILABLE",
            "STAGING_RUNTIME_ENV=PRESENT_NOT_READ",
            "STAGING_DOCTOR=READ_ONLY_COMPLETE",
        ):
            self.assertIn(marker, source)

    def test_never_mutates_or_reads_credentials(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for forbidden in (
            "systemctl start", "systemctl enable", "systemctl restart",
            "systemctl reload", "git reset", "git clean", "git checkout",
            "git fetch", "artisan migrate", "artisan optimize",
            "rm -rf", "ln -s", "mv -T", "curl -k", "source .env",
            "cat .env", "cat \"$worker\"", "sed -n",
        ):
            self.assertNotIn(forbidden, source)

if __name__ == "__main__":
    unittest.main()
