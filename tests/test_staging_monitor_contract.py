from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEPLOY_WORKFLOW = ROOT / ".github" / "workflows" / "staging-vps-deploy-fixed.yml"
RECOVERY_WORKFLOW = ROOT / ".github" / "workflows" / "staging-deploy-recovery.yml"
AUTH_SMOKE_WORKFLOW = ROOT / ".github" / "workflows" / "staging-authenticated-smoke.yml"
DELIVERY_FINALIZER_WORKFLOW = ROOT / ".github" / "workflows" / "delivery-status-finalizer.yml"
BOOTSTRAP = ROOT / "apps" / "platform" / "bootstrap" / "app.php"
SERVER_BOOTSTRAP = ROOT / "infra" / "server" / "KMJ_SERVER_BOOTSTRAP.sh"


class StagingMonitorContractTests(unittest.TestCase):
    def test_public_monitoring_routes_are_not_registered_on_live_surface(self):
        bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
        self.assertNotIn("routes/staging-monitoring.php", bootstrap)

    def test_staging_deploy_uses_public_exact_sha_evidence_without_ssh(self):
        workflow = DEPLOY_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("x-kmj-deploy-sha", workflow.lower())
        self.assertIn("VPS systemd auto-deploy timer", workflow)
        self.assertIn("https://staging.kmjtechno.com/products", workflow)
        self.assertIn(
            "https://staging.kmjtechno.com/products/kmj-calibration-pro",
            workflow,
        )
        self.assertIn("assert_dom 'root' 'Explore KMJ products'", workflow)
        self.assertIn("assert_dom 'products' 'Explore product'", workflow)
        self.assertIn("Staging UI assertion failed", workflow)
        self.assertNotIn("STAGING_SSH_PRIVATE_KEY", workflow)
        self.assertNotIn("ssh -i", workflow)
        self.assertNotIn("ops/staging/verify-monitor.py", workflow)
        self.assertNotIn("https://staging.kmjtechno.com/info", workflow)

    def test_server_bootstrap_remains_the_staging_deploy_authority(self):
        bootstrap = SERVER_BOOTSTRAP.read_text(encoding="utf-8")

        self.assertIn('DEPLOY_BRANCH="${KMJ_DEPLOY_BRANCH:-staging-approved}"', bootstrap)
        self.assertIn("kmj-stage-deploy.timer", bootstrap)
        self.assertIn("OnUnitActiveSec=2min", bootstrap)
        self.assertIn(r'SUCCESS_FILE="\$HOME/.kmj-stage-last-success"', bootstrap)
        self.assertIn(r'git -C "\$REPO_DIR" reset --hard "origin/\$BRANCH"', bootstrap)

    def test_authenticated_surface_smoke_no_longer_depends_on_vps_ssh(self):
        workflow = AUTH_SMOKE_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("runs-on: ubuntu-latest", workflow)
        self.assertIn("staging:smoke-authenticated-surfaces", workflow)
        self.assertIn("DB_CONNECTION: sqlite", workflow)
        self.assertNotIn("STAGING_SSH_PRIVATE_KEY", workflow)
        self.assertNotIn("ssh -i", workflow)

    def test_staging_recovery_no_longer_depends_on_offline_runner(self):
        workflow = RECOVERY_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("runs-on: ubuntu-latest", workflow)
        self.assertNotIn("kmj-main-platform-ci", workflow)
        self.assertIn("rerun-failed-jobs", workflow)

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
