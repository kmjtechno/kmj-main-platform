# KMJ DevForge — Super Admin control MVP

This is a private host service; not yet a full GitHub replacement or an AI worker fleet.

## Security contract

- Web route /operator/devforge uses auth, verified, password.confirm and PlatformOwnerAccess.
- PlatformOwnerAccess enforces owner status, verified email and a registered passkey.
- Local Unix socket: /run/kmj-devforge/control.sock. Only fixed actions install/start/stop/restart.
- The host broker validates the peer UID and accepts no user paths, commands, URLs, tokens or shell.
- Health comes from the live Gitea /api/healthz endpoint; action accepted is not a claim of readiness.
- Private loopback-only Gitea rootless 1.27.3, no open registrations, no Actions runners.
- Initial Gitea admin credentials stored root-only in /var/lib/kmj-devforge/initial-admin-credentials.txt.

## Bootstrap once after PR merge, CI acceptance and reviewed platform release

1. Identify the actual PHP-FPM user on KMJ-elite. Check Docker Engine and Compose v2.
2. As root from the deployed repo run: bash infra/devforge/bootstrap-kmj-elite.sh
3. The bootstrap discovers the single non-root PHP-FPM user, and stops if ambiguous. You may explicitly set DEVFORGE_WEB_USER only after verifying the effective application pool identity.
4. Verify systemctl is-active kmj-devforge-broker.service equals active.
5. Open Main Platform Super Admin -> KMJ DevForge and click One-click setup.
6. Poll until the control center reports healthy; errors are shown as static codes.
7. Use an SSH local tunnel to view the private forge: ssh -L 3030:127.0.0.1:3030 root@YOUR_SERVER
8. Open http://localhost:3030/ and retrieve initial admin credentials only on host.

## Safety gates and known limitations

- This script does not modify production Nginx, DNS, payments, licensing, Git repos or CodeBridge agents.
- No automatic GitHub mirroring, external HTTPS, SSH clone endpoint, LFS throughput benchmark, backup/restore or CI execution has been enabled.
- Before storing critical private repositories: add durable offsite snapshots, SQLite-consistent backup/restore proof, authentication and access review.
- Rootless and rootful Gitea volume layouts are not interchangeable.
- Docker runs with daemon privileges inside the fixed root broker; never expose the broker socket or Docker socket over the network.
- A stopped service retains its volumes and can be started again.
- Do not modify CodeBridge job concurrency limits without the signed entitlement and agent capacity checks.
- Never claim the new Super Admin page is live until the exact source SHA is merged, deployed and browser-tested.

## Current independent QA blockers (2026-10-17)

- GitHub Actions 6/6 selected PR workflows report failure; detailed remote job logs could not be retrieved (BlobNotFound / unavailable). Never infer that PHP, Rust or frontend code failed from a missing log.
- CodeBridge `main_platform_ui_ci:check` on isolated existing main SHA eb676253 failed exit 127 (`vp: not found`), before any new PR source was tested.
- Explicit fixed `main_platform_ui_deps:ci` on the isolated existing main worktree failed exit 226 with npm ENOENT/TAR_ENTRY_ERROR; output truncated. Do not treat that as DevForge code failure or claim a green exact-head gate.
- `verify-offline.sh` offers a dedicated Python broker unittest and basic PHP/Bash syntax suite; full exact-HEAD build and Laravel tests remain required.
- Security: the Unix socket grants fixed actions to the effective PHP-FPM UID. If that UID is shared by another application, that app can call the broker directly. Production activation requires a dedicated isolated PHP-FPM pool or equivalent audited host boundary; a Laravel owner gate alone does not prevent same-UID local callers.
- No production merge, DNS publication, external CI runner enrollment, backup/restore qualification, or host activation has occurred.
