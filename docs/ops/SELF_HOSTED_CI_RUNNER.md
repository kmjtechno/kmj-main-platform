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

## Staging delivery

The staging VPS owns deployment through its systemd `kmj-stage-deploy.timer`. The timer consumes only the machine-maintained `staging-approved` branch and serializes writes with the server-local deployment lock. GitHub Actions no longer needs a reusable VPS SSH private key to force a deployment.

`Staging VPS Deploy` runs on GitHub-hosted Ubuntu and verifies the exact approved commit through the staging-only `X-KMJ-Deploy-SHA` response header. The middleware emits that header only for `staging.kmjtechno.com`, derives it from the checked-out repository metadata without executing a shell, and never exposes it on the production host. The workflow waits for the timer to converge, then runs HTTP health, rendered UI checks, and desktop/mobile browser QA.

Authenticated route smoke also runs on GitHub-hosted Ubuntu against the same approved commit with an isolated SQLite database and transaction-scoped synthetic owner. This separates authenticated source regression from live public deployment proof while removing the stale SSH-key dependency.

The self-hosted runner remains available for workflows that genuinely require its local AI/runtime environment, but staging deployment verification and bounded recovery do not depend on it.
