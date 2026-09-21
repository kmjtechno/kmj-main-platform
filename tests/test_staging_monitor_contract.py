from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEPLOY_WORKFLOW = ROOT / ".github" / "workflows" / "staging-vps-deploy-fixed.yml"
DELIVERY_FINALIZER_WORKFLOW = ROOT / ".github" / "workflows" / "delivery-status-finalizer.yml"
BOOTSTRAP = ROOT / "apps" / "platform" / "bootstrap" / "app.php"


class StagingMonitorContractTests(unittest.TestCase):
    def test_public_monitoring_routes_are_not_registered_on_live_surface(self):
        bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
        self.assertNotIn("routes/staging-monitoring.php", bootstrap)

    def test_staging_deploy_verifies_public_products_instead_of_monitor(self):
        workflow = DEPLOY_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("https://staging.kmjtechno.com/products", workflow)
        self.assertIn("https://staging.kmjtechno.com/products/kmj-calibration-pro", workflow)
        self.assertNotIn("ops/staging/verify-monitor.py", workflow)
        self.assertNotIn("https://staging.kmjtechno.com/info", workflow)

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

    def test_worker_completion_has_delivery_status_finalizer(self):
        workflow = DELIVERY_FINALIZER_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("workflow_run:", workflow)
        self.assertIn('workflows: ["Autonomous Execution Worker"]', workflow)
        self.assertIn("types: [completed]", workflow)
        self.assertIn("scripts/delivery_control_bridge.py", workflow)
        self.assertIn(
            "runs-on: [self-hosted, linux, x64, kmj-main-platform-ci]",
            workflow,
        )


if __name__ == "__main__":
    unittest.main()
