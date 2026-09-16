from __future__ import annotations

import io
import json
import runpy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "ops" / "staging" / "verify-monitor.py"
DEPLOY_WORKFLOW = ROOT / ".github" / "workflows" / "staging-vps-deploy-fixed.yml"
ORIGIN = "https://staging.kmjtechno.com"


class FakeResponse(io.BytesIO):
    def __init__(self, payload: dict, url: str):
        super().__init__(json.dumps(payload).encode("utf-8"))
        self.status = 200
        self._url = url

    def geturl(self) -> str:
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


class StagingMonitorContractTests(unittest.TestCase):
    def test_verifier_accepts_delivery_control_monitor_component(self):
        def fake_urlopen(request, timeout=20):
            url = request.full_url
            if url == ORIGIN + "/info":
                return FakeResponse(
                    {"component": "info-control", "props": {"pollIntervalMs": 5000}},
                    url,
                )
            if url == ORIGIN + "/info/status":
                return FakeResponse(
                    {
                        "status": "healthy",
                        "runtime": {"application": True, "database": True},
                        "deployment": {"deployed_sha": "d" * 40},
                    },
                    url,
                )
            raise AssertionError(f"unexpected URL: {url}")

        with (
            patch("urllib.request.urlopen", side_effect=fake_urlopen),
            patch.object(sys, "argv", [str(SCRIPT)]),
        ):
            runpy.run_path(str(SCRIPT), run_name="__main__")

    def test_staging_deploy_refreshes_local_path_packages_before_composer_install(self):
        workflow = DEPLOY_WORKFLOW.read_text()
        install = (
            'COMPOSER_PHP="$PHP_BIN" composer install --no-interaction '
            '--prefer-dist --no-progress --no-dev --optimize-autoloader --no-scripts'
        )
        install_index = workflow.index(install)
        for package in (
            "domain-organizations",
            "domain-catalog",
            "domain-entitlements",
            "domain-commerce",
        ):
            path = f"vendor/kmjtechno/{package}"
            self.assertIn(path, workflow)
            self.assertLess(workflow.index(path), install_index)

    def test_staging_deploy_fails_closed_when_required_org_context_is_missing(self):
        workflow = DEPLOY_WORKFLOW.read_text()
        install = (
            'COMPOSER_PHP="$PHP_BIN" composer install --no-interaction '
            '--prefer-dist --no-progress --no-dev --optimize-autoloader --no-scripts'
        )
        install_index = workflow.index(install)
        guard_index = workflow.index("class_exists")
        guard_line = next(line for line in workflow.splitlines() if "class_exists" in line)
        while "\\\\" in guard_line:
            guard_line = guard_line.replace("\\\\", "\\")
        class_name = r"KMJ\MainPlatform\Organizations\Services\OrganizationCapabilityContext"

        self.assertIn(class_name, guard_line)
        self.assertGreater(guard_index, install_index)
        self.assertIn("exit 47", workflow)


if __name__ == "__main__":
    unittest.main()
