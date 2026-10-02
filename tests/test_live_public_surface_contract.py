from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "apps/platform/bootstrap/app.php"
WELCOME = ROOT / "apps/platform/resources/js/pages/welcome.tsx"
APP_VIEW = ROOT / "apps/platform/resources/views/app.blade.php"
FAVICON = ROOT / "apps/platform/public/kmj-favicon-20261002.png"
LOCKED_APP_ICON = ROOT / "apps/platform/public/assets/brand/kmj-app-icon.png"
DEPLOY = ROOT / ".github/workflows/staging-vps-deploy-fixed.yml"
HEALTH = ROOT / ".github/workflows/self-hosted-runner-health.yml"
BROWSER_QA = ROOT / "ops/staging/browser-qa.mjs"


class LivePublicSurfaceContractTests(unittest.TestCase):
    def test_public_monitor_route_file_is_not_registered(self):
        bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
        self.assertNotIn("routes/staging-monitoring.php", bootstrap)

    def test_public_home_has_no_staging_or_monitor_badges(self):
        welcome = WELCOME.read_text(encoding="utf-8")
        for marker in ("Live staging", "Staging live", "Staging Preview"):
            self.assertNotIn(marker, welcome)

    def test_public_shell_uses_locked_kmj_favicon(self):
        app_view = APP_VIEW.read_text(encoding="utf-8")
        locked_icon = "/kmj-favicon-20261002.png"

        self.assertIn(
            f'rel="icon" type="image/png" sizes="512x512" href="{locked_icon}"',
            app_view,
        )
        self.assertIn(
            f'rel="shortcut icon" type="image/png" href="{locked_icon}"',
            app_view,
        )
        self.assertIn(f'rel="apple-touch-icon" href="{locked_icon}"', app_view)
        self.assertNotIn('href="/favicon.ico"', app_view)
        self.assertNotIn('href="/favicon.svg"', app_view)
        self.assertTrue(FAVICON.is_file())
        self.assertEqual(FAVICON.read_bytes(), LOCKED_APP_ICON.read_bytes())

    def test_deploy_and_health_checks_do_not_depend_on_public_info_monitor(self):
        deploy = DEPLOY.read_text(encoding="utf-8")
        health = HEALTH.read_text(encoding="utf-8")
        browser = BROWSER_QA.read_text(encoding="utf-8")

        self.assertNotIn("ops/staging/verify-monitor.py", deploy)
        self.assertNotIn("staging.kmjtechno.com/info", deploy)
        self.assertNotIn("staging.kmjtechno.com/info", health)
        self.assertNotIn("{ path: '/info'", browser)


if __name__ == "__main__":
    unittest.main()
