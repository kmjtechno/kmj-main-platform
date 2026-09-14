# KMJ Main Platform self-hosted CI runner

This runner is for `kmjtechno/kmj-main-platform` CI only. Do not share it with KMJ Cloud Nexus or production application processes.

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
