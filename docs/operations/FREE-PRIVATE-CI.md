# KMJ Main Platform: private CI at zero extra GitHub cost

## Why this exists

The private `kmjtechno/kmj-main-platform` GitHub repository currently has hosted jobs that fail **before any step executes**. They do **not** show that the Laravel, React/TypeScript, CodeBridge OAuth, pairing, or Rust tests passed or failed.

The customer work is in [PR #325](https://github.com/kmjtechno/kmj-main-platform/pull/325). Do not deploy it without real exact-head CI evidence.

**Cost policy:** no paid Actions minutes, no billing top-up, no larger hosted runner, no new paid server. GitHub currently lists **self-hosted Actions runner usage as free**. Existing VM power, storage and network are still your responsibility.

## Easiest safe setup

Use a **dedicated testing VM that you already own**, not the production website/VPS, and not `device1/project1`. This runner executes repository code, so isolate it from production credentials, database mounts, SSH keys, Docker socket and deployment keys. Restrict access to trusted branches; fork PRs are kept on GitHub-hosted runners instead.

1. On GitHub (same personal account as the private repository), open:
   [Settings → Actions → Runners](https://github.com/kmjtechno/kmj-main-platform/settings/actions/runners).
2. If the `kmj-main-platform-ci` runner is already **Online**, do not reinstall or replace it. The new CI workflow chooses its label automatically.
3. Otherwise click **New self-hosted runner** → **Linux** → **x64**.
4. On the dedicated testing VM, follow the **official GitHub download + configure commands** shown on that page. Use a dedicated non-root account. During registration specify the additional custom label `kmj-main-platform-ci`. Do not use `--replace` or share the short-lived registration token in a chat, issue, screenshot or commit.
5. To use the repository's verified install script instead, have an authorized checkout of this branch on the testing VM and run:
   
   ```bash
   sudo bash ops/self-hosted-runner/preflight-zero-cost-ci.sh
   sudo bash ops/self-hosted-runner/install-kmj-runner.sh
   ```
   
   The installer prompts invisibly for the one-time registration token. It refuses to overwrite existing runner credentials and pins the runner archive to its SHA-256 checksum. The preflight is read-only. Do not paste the token as a shell argument.
6. The VM needs PHP 8.4 with SQLite/Sodium, Composer, Node.js 22/24, Git, Python 3, Rustup/Cargo and the required PHP extensions. The CI workflows deliberately skip the privileged PHP setup action on self-hosted machines; toolchains must be provisioned on the isolated VM beforehand.
7. Ensure GitHub shows **Online** and custom label `kmj-main-platform-ci). The PR CI jobs for trusted branches can then run without spending GitHub-hosted minutes.

The `kmj-main-platform-ci` label is intentionally required; a generic self-hosted runner cannot accidentally receive the private build.

## CI selection and fork safety

These existing workflows now select the free testing runner when trusted repository code runs:

- KMJ Main Platform CI (Laravel/TypeScript and Rust)
- CodeBridge License Contract
- Platform Runtime CI
- CodeBridge OAuth CI
- CodeBridge Device Pairing CI
- Verify Foundation

A PR originating from a different repository continues to use `ubuntu-latest` rather than running untrusted fork code on your private VM. All other production, deploy and autonomous workflows stay unchanged.

## Exact-head release gate

After the runner is online:

1. Confirm all required checks actually execute steps instead of immediately failing with `steps: []`.
2. Verify dependency installation, PHP tests/Pint, JS/TS build/lint/typecheck, Rust, CodeBridge OAuth/pairing and security contracts on **the latest PR #325 commit**.
3. Diagnose and fix any real failing assertions rather than disabling tests.
4. Merge only when every required check on that exact head is green.
5. Deploy first to staging, check login, customer organization switching, 1–10 product bundle order lifecycle, device list privacy, locked KMJ TECHNO logo and safe downloads. Production remains approval-gated.

If the GitHub repository is on an unsupported legacy per-repository plan, or self-hosted jobs are also blocked at zero steps, GitHub account support/settings must be resolved. This cannot be fixed by changing PHP/React code.

## Safety invariants

- Never use a production server, live credentials, primary database or the existing `device1/project1` environment as an untrusted job runner.
- Never expose the one-time registration token.
- Never remove or replace an existing runner enrollment to make installation appear successful.
- Never turn the private repository public to evade billing.
- Runner online only proves capacity; actual exact-head CI success is required.
