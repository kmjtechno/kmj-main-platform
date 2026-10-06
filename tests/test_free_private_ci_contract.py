"""Zero-extra-cost private CI contract; pure stdlib, no GitHub token or network."""

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
LABEL = "kmj-main-platform-ci"
RUNNER_EXPRESSION = "runs-on: [self-hosted, linux, x64, kmj-main-platform-ci]"
FORK_GUARD = (
    "if: github.event_name != 'pull_request' || "
    "github.event.pull_request.head.repo.full_name == github.repository"
)
REQUIRED_WORKFLOWS = {
    "kmj-main-platform-ci.yml": 2,
    "codebridge-contract.yml": 2,
    "platform-ci.yml": 1,
    "codebridge-oauth-link-ci.yml": 1,
    "codebridge-device-pairing-ci.yml": 1,
    "verify.yml": 1,
}


class FreePrivateCiContract(unittest.TestCase):
    def test_eight_existing_jobs_select_trusted_self_hosted_runner(self):
        count = 0
        for filename, jobs in REQUIRED_WORKFLOWS.items():
            source = (ROOT / ".github" / "workflows" / filename).read_text()
            self.assertEqual(
                source.count(RUNNER_EXPRESSION),
                jobs,
                msg=f"{filename} must use the free isolated runner",
            )
            # Forks must be skipped entirely: no private runner, no paid minutes.
            self.assertEqual(
                source.count(FORK_GUARD),
                jobs,
                msg=f"{filename} must skip all fork jobs",
            )
            self.assertNotIn("runs-on: ubuntu-latest", source)
            count += jobs
        self.assertEqual(count, 8)

    def test_hosted_only_php_installer_does_not_change_private_vm(self):
        for filename in REQUIRED_WORKFLOWS:
            source = (ROOT / ".github" / "workflows" / filename).read_text()
            if "shivammathur/setup-php@" in source:
                self.assertIn(
                    "if: runner.environment == 'github-hosted'",
                    source,
                    msg=filename,
                )

    def test_installer_never_replaces_credentials_and_prompts_privately(self):
        installer = (
            ROOT / "ops" / "self-hosted-runner" / "install-kmj-runner.sh"
        ).read_text()
        self.assertIn('read -r -s -p', installer)
        self.assertNotIn("--replace", installer)
        self.assertIn('Existing runner registration found', installer)
        self.assertIn('kmj-main-platform-ci', installer)
        self.assertIn("sha256sum -c -", installer)
        self.assertIn("umask 077", installer)

    def test_readonly_preflight_and_explicit_user_approval(self):
        preflight = (
            ROOT / "ops" / "self-hosted-runner" / "preflight-zero-cost-ci.sh"
        ).read_text()
        self.assertNotRegex(preflight, r"\b(?:apt-get|chown|chmod|systemctl start)\b")
        documentation = (
            ROOT / "docs" / "operations" / "FREE-PRIVATE-CI.md"
        ).read_text()
        self.assertIn("Do not paste the token", documentation)
        self.assertIn("Do not use", documentation)
        self.assertIn("production", documentation)


if __name__ == "__main__":
    unittest.main()
