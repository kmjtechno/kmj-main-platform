# KMJ Main Platform self-hosted CI runner

This runner pool is for `kmjtechno/kmj-main-platform` CI and approved staging delivery. Do not share it with KMJ Cloud Nexus or production application processes.

## Security boundary

- Dedicated Linux account: `kmjrunner`
- Dedicated runner directory: `/opt/kmj-actions-runner`
- Repository-scoped registration only
- Required custom label: `kmj-main-platform-ci`
- No production deployment secrets in the runner environment
- Do not run untrusted fork pull requests on this runner
- Registration token is ephemeral and must never be committed or logged

## Install

Generate a repository-scoped self-hosted runner registration token in GitHub, then on the authorized CI host run:

```bash
export RUNNER_TOKEN='<ephemeral-registration-token>'
sudo -E bash ops/self-hosted-runner/install-kmj-runner.sh
```

The installer registers the labels `self-hosted`, `linux`, `x64`, and `kmj-main-platform-ci`, installs the runner as a system service, starts it, and prints service status.

## Verification gate

Run the `Self-Hosted Runner Health` workflow manually. It must complete on the `kmj-main-platform-ci` runner before any authoritative CI workflow is migrated from `ubuntu-latest`.

Only after the health gate is green should `Platform Runtime CI` and `Verify Foundation` be switched to the dedicated self-hosted label. Until then GitHub-hosted workflows remain unchanged so existing CI semantics do not regress.

## Staging delivery on the existing runner pool

Staging deploy, bounded recovery and authenticated smoke use the repository-scoped `kmj-main-platform-ci` pool. They continue to consume only `staging-approved`; production access is not introduced. Deployment keys exist only in per-run directories under `runner.temp` and are removed in an `always()` step.

The health workflow verifies SSH clients, public staging responses and a real headless browser launch. `ops/self-hosted-runner/prepare-staging-browser.sh` downloads the pinned official Chrome for Testing headless shell into the runner tool cache without sudo. On Ubuntu 24.04, missing desktop libraries are downloaded through the configured authenticated APT indexes and extracted into the browser cache; no package installation or maintainer scripts run. Library paths apply only to the browser wrapper. The health gate still requires a successful browser launch. This does not install system packages or change the host configuration.

The deployment workflow must pass the existing rendered homepage check plus `ops/staging/verify-monitor.py`, which checks the Inertia monitor component and matches the public deployed SHA to the approved commit. A successful HTTP response alone is insufficient proof of rollout.
