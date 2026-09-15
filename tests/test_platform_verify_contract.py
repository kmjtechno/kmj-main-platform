import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "ops/self-hosted-runner/verify-platform.sh"

FAKE_TOOL = r"""#!/usr/bin/env python3
import os
from pathlib import Path
import sys
import time
name = Path(sys.argv[0]).name
args = sys.argv[1:]
state = Path(os.environ["KMJ_TEST_STATE"])
def mark(value):
    (state / value).touch()
def wait_for(value):
    end = time.monotonic() + 3
    while not (state / value).exists():
        if time.monotonic() > end:
            raise SystemExit("Parallel peer did not start: " + value)
        time.sleep(0.02)
if name == "composer" and args[0] == "install":
    mark("composer-install")
    wait_for("npm-install")
    if os.environ.get("KMJ_TEST_FAIL") == "install":
        raise SystemExit(1)
elif name == "npm" and args[0] in ("ci", "install"):
    assert "--prefer-offline" in args
    mark("npm-install")
    wait_for("composer-install")
elif name == "npm" and args == ["run", "build"]:
    mark("build")
elif name == "composer" and args[0] == "test":
    assert (state / "build").exists()
    mark("php-check")
    wait_for("frontend-check")
    if os.environ.get("KMJ_TEST_FAIL") == "php":
        raise SystemExit(1)
elif name == "vp":
    assert (state / "build").exists()
    mark("frontend-check")
    wait_for("php-check")
elif name == "npm" and args == ["run", "types:check"]:
    mark("types-check")
"""

class PlatformVerificationContractTests(unittest.TestCase):
    def run_pipeline(self, fail="", database_matches=True):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            platform = root / "apps/platform"
            (platform / "database").mkdir(parents=True)
            (platform / "node_modules/.bin").mkdir(parents=True)
            for name in ("composer.lock", "package.json", ".env.example"):
                (platform / name).write_text("{}")
            binary = root / "bin"
            binary.mkdir()
            state = root / "state"
            state.mkdir()
            for name in ("composer", "npm", "php"):
                path = binary / name
                path.write_text(FAKE_TOOL)
                path.chmod(0o755)
            vp = platform / "node_modules/.bin/vp"
            vp.write_text(FAKE_TOOL)
            vp.chmod(0o755)
            env = {
                **os.environ,
                "PATH": str(binary) + os.pathsep + os.environ["PATH"],
                "GITHUB_WORKSPACE": str(root),
                "RUNNER_TEMP": str(root),
                "DB_CONNECTION": "sqlite",
                "DB_DATABASE": str(platform / "database/database.sqlite")
                if database_matches else str(root / "other.sqlite"),
                "KMJ_TEST_STATE": str(state),
                "KMJ_TEST_FAIL": fail,
            }
            result = subprocess.run(
                ["bash", str(SCRIPT)], env=env, text=True,
                capture_output=True, timeout=15,
            )
            return result, {path.name for path in state.iterdir()}

    def test_independent_installs_and_checks_overlap(self):
        result, events = self.run_pipeline()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Platform verification PASS", result.stdout)
        self.assertTrue({"build", "php-check", "frontend-check", "types-check"} <= events)

    def test_install_failure_prevents_build_and_checks(self):
        result, events = self.run_pipeline(fail="install")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("build", events)
        self.assertNotIn("Platform verification PASS", result.stdout)

    def test_failed_php_lane_cannot_pass_with_green_frontend(self):
        result, events = self.run_pipeline(fail="php")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("types-check", events)
        self.assertNotIn("Platform verification PASS", result.stdout)

    def test_database_outside_ci_checkout_is_rejected(self):
        result, events = self.run_pipeline(database_matches=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(events, set())


if __name__ == "__main__":
    unittest.main()
