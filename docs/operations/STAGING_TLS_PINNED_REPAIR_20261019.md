# KMJ staging TLS repair: operator trust and production isolation

**19 October 2026 evidence:** GitHub staging exact SHA readback run 39242853781 was blocked by TLS SAN mismatch on `staging.kmjtechno.com`. Cloudflare DNS for that hostname is a DNS-only A record to **103.212.136.154**. A protected staging TLS repair workflow was added in PR #485; its first action run 39243921990 failed **before connecting to any server** because old `STAGING_SSH_HOST` did not match the verified staging IP. The `STAGING_SSH_KNOWN_HOSTS` secret was also empty. Do not report TLS repaired or staging deployed.

The workflow now pins the reviewed staging IP as source code; it does not use the old SSH host secret. This does **not** grant SSH trust. A trusted operator must securely verify and provision the host's real public SSH host key for this fixed endpoint.

## Only remaining one-time trust dependency

From an **already trusted** KMJ-elite console or previously authenticated known-good SSH connection (not a first-use `ssh-keyscan`), an authorized operator can inspect `/etc/ssh/ssh_host_ed25519_key.pub` and independently verify its fingerprint. The public Ed25519 host key is *not a private SSH login key*. Create/update the GitHub **staging environment** Actions secret named `STAGING_SSH_KNOWN_HOSTS` with one validated known-hosts line for the SSH endpoint:

    103.212.136.154 ssh-ed25519 <the independently verified server public host key>

Never invent or copy the key from an unverified internet scan. Never put login private keys or backup-age identities into issues, chat or commit history. Existing `STAGING_SSH_USER` and `STAGING_SSH_PRIVATE_KEY` remain restricted to the authorized staging environment; verify these values are current without displaying them.

[GitHub Staging Environment Settings](https://github.com/kmjtechno/kmj-main-platform/settings/environments): select the existing staging environment, then Environment secrets. No upgrade is needed for this source change.

## Exact runbook after trust exists

Trigger `Staging P0 TLS Repair (Pinned Host)` from GitHub Actions. This workflow checks the protected current repo `infra/server/KMJ_STAGE_TLS_REPAIR.sh` checksum against the exact fixed script already present at `/root/KMJ_STAGE_TLS_REPAIR.sh` on KMJ-elite, and refuses mismatches. It verifies `/home/kmjprod/current` remains the same before/after. The pinned operator script changes only the staging vhost Let's Encrypt certificate and does an nginx reload; it refuses other hostnames and DNS mismatch. Finally, externally validate normal HTTPS with curl **without `-k`**.

If the remote root-owned script is absent or mismatched, install it through a separately reviewed privileged maintenance operation first; never fetch-and-execute an unpinned script. A certificate repair is not authority to activate a production release, change Main Platform approval JSON, or bypass backup/rollback/owner QA. Production status stays blocked unless its own protected supervisor returns `readyToActivate=true`.

## Independent go-live dependencies

Separate from TLS: real encrypted offsite database+storage restore into a disposable PostgreSQL host; immutable clean production candidate at `/home/kmjprod/releases/platform-<sha12>`; root-owned backup witness and approved manifest `/etc/kmj-codebridge/main-platform-production-release.json` reflecting current live pointer and **actual** validated backup and rollback; authenticated owner-browser QA. Do not claim any of these complete from source CI or staging HTTPS alone. Email remains explicitly outside this workstream.
