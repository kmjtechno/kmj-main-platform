from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/staging-vps-deploy-fixed.yml"


class StagingPathPackageRefreshContractTests(unittest.TestCase):
    def setUp(self):
        self.workflow = WORKFLOW.read_text()
        self.install = (
            'COMPOSER_PHP="$PHP_BIN" composer install --no-interaction '
            '--prefer-dist --no-progress --no-dev --optimize-autoloader --no-scripts'
        )

    def test_local_path_packages_are_refreshed_before_composer_install(self):
        install_index = self.workflow.index(self.install)
        for package in (
            "domain-organizations",
            "domain-catalog",
            "domain-entitlements",
            "domain-commerce",
        ):
            path = f"vendor/kmjtechno/{package}"
            self.assertIn(path, self.workflow)
            self.assertLess(self.workflow.index(path), install_index)

    def test_required_organization_context_is_verified_after_install(self):
        install_index = self.workflow.index(self.install)
        class_name = (
            "KMJ\\\\MainPlatform\\\\Organizations\\\\Services\\\\"
            "OrganizationCapabilityContext"
        )
        self.assertIn("class_exists", self.workflow)
        self.assertIn(class_name, self.workflow)
        self.assertGreater(self.workflow.index("class_exists"), install_index)
        self.assertGreater(self.workflow.index(class_name), install_index)


if __name__ == "__main__":
    unittest.main()
