# KMJ staging TLS repair: operator trust and production isolation

**19 October 2026 evidence:** GitHub staging exact SHA readback run 39242853781 was blocked by TLS SAN mismatch on `staging.kmjtechno.com`. Cloudflare DNS for that hostname is a DNS-only A record to **103.212.136.154**. A protected staging TLS repair workflow was added in PR #485; its first action run 39243921990 failed **before connecting to any server** because old `STAGING_SSH_HOST` did not match the verified staging IP. The `STAGING_SSH_KNOWN_HOSTS` secret was also empty. Do not report TLS repaired or staging deployed.

The workflow pins the staging host IP in source code. On 19 October 2026 the owner provided the Ed25519 **public host key** directly from an authenticated `root@KMJ-elite` console. The reviewed `known_hosts` line is committed at `infra/server/trust/kmj-elite-staging-known_hosts`; it is a public server identity, **not** a private SSH login credential.

The trust check remains `StrictHostKeyChecking=yes` with exactly one source-pinned host key. We do **not** use `ssh-keyscan` or a host key obtained on first connection, do not downgrade certificate validation, and no longer require `STAGING_SSH_KNOWN_HOSTS` environment secret. The previous missing host-key-secret blocker is fixed at source level. Host key rotation must be verified from the console before modifying this file, followed by normal PR review and exact-head CI.

The staging GitHub Environment still needs valid `STAGING_SSH_USER` and `STAGING_SSH_PRIVATE_KEY` (already configured previously). These are login credentials, never to be pasted into issues or committed. A pinned public host key does not grant login permission.

## Previously observed failure

Staging readback Action 39242853781 failed because the certificate did not cover `staging.kmjtechno.com`. Earlier guarded repair runs failed closed first on a stale SSH host secret and then on absent `STAGING_SSH_KNOWN_HOSTS`. These are past observations only: source correction is not proof that the new release's live repair succeeded. Read the latest guarded workflow logs and externally verify normal TLS and exact SHA before declaring a production-ready stage.

## Exact runbook after trust exists

Trigger `Staging P0 TLS Repair (Pinned Host)` from GitHub Actions. This workflow checks the protected current repo `infra/server/KMJ_STAGE_TLS_REPAIR.sh` checksum against the exact fixed script already present at `/root/KMJ_STAGE_TLS_REPAIR.sh` on KMJ-elite, and refuses mismatches. It verifies `/home/kmjprod/current` remains the same before/after. The pinned operator script changes only the staging vhost Let's Encrypt certificate and does an nginx reload; it refuses other hostnames and DNS mismatch. Finally, externally validate normal HTTPS with curl **without `-k`**.

If the remote root-owned script is absent or mismatched, install it through a separately reviewed privileged maintenance operation first; never fetch-and-execute an unpinned script. A certificate repair is not authority to activate a production release, change Main Platform approval JSON, or bypass backup/rollback/owner QA. Production status stays blocked unless its own protected supervisor returns `readyToActivate=true`.

## Independent go-live dependencies

Separate from TLS: real encrypted offsite database+storage restore into a disposable PostgreSQL host; immutable clean production candidate at `/home/kmjprod/releases/platform-<sha12>`; root-owned backup witness and approved manifest `/etc/kmj-codebridge/main-platform-production-release.json` reflecting current live pointer and **actual** validated backup and rollback; authenticated owner-browser QA. Do not claim any of these complete from source CI or staging HTTPS alone. Email remains explicitly outside this workstream.
