# KMJ Main Platform — Reproducible Staging Server

This directory is the source of truth for rebuilding the **KMJ TECHNO Main Platform staging server**. It exists so a VPS replacement does not require repeating the manual recovery sequence used during the first staging build.

## Locked boundaries

- Main Platform only.
- Production `kmjtechno.com` is not changed by this bootstrap.
- Default staging hostname: `staging.kmjtechno.com`.
- Deployment source: machine-maintained `staging-approved`, not raw `main`.
- `staging-approved` is advanced only by the repository's Staging Promotion Gate after verification succeeds.
- KMJ Cloud Nexus is a separate project and is untouched.
- PostgreSQL listens only on `127.0.0.1`.
- The generated GitHub deploy key is read-only.
- Staging stays `noindex` through `robots.txt`.
- Secrets are generated on the server and are never committed.

## New server recovery model

The stable entrypoint is `KMJ_SERVER_BOOTSTRAP.sh`.

**Do not create V2/V3 copies.** If a phase fails, fix the cause and rerun the same file. The script is designed to be idempotent and resumable.

Typical future migration:

1. Provision a fresh **Ubuntu 24.04 LTS amd64** VPS.
2. Copy `KMJ_SERVER_BOOTSTRAP.sh` to `/root/KMJ_SERVER_BOOTSTRAP.sh`.
3. Run:
   ```bash
   chmod +x /root/KMJ_SERVER_BOOTSTRAP.sh
   bash /root/KMJ_SERVER_BOOTSTRAP.sh
   ```
4. The bootstrap installs/reconciles CloudPanel, PHP 8.5, PostgreSQL 18, Node 22, Rust, firewall, swap, deployment worker, systemd timer and credentials.
5. If the newly generated GitHub deploy key is not yet authorized, the script stops in a safe `ACCOUNT_ACTION_PENDING` state and writes `/root/KMJ_SERVER_NEXT_ACTIONS.txt`. Add that public key as a **read-only deploy key**, then rerun the same bootstrap.
6. Point the staging A record to the new VPS. Rerun the same bootstrap. It installs Let's Encrypt when DNS resolves.
7. Run `KMJ_SERVER_VERIFY.sh`. A server is accepted only when it returns `FAIL=0`.

This intentionally leaves two account-level actions outside the server itself: authorizing a new GitHub read-only deploy key and changing DNS. They are external trust/account controls and should not be silently automated with long-lived credentials.

## Supply-chain behavior

The CloudPanel installer is checksum-pinned. If CloudPanel publishes a new installer, bootstrap fails closed instead of downloading an unverified replacement. Verify the new checksum against CloudPanel's official installation documentation, then run the same bootstrap with:

```bash
KMJ_CLOUDPANEL_SHA256=<verified-sha256> bash /root/KMJ_SERVER_BOOTSTRAP.sh
```

PostgreSQL 18 is installed from PostgreSQL's PGDG repository for the current Ubuntu codename.

## Generated server-local files

- `/root/.kmj-server-secrets` — server secrets, mode 600. Never share.
- `/root/KMJ_SERVER_CREDENTIALS.txt` — human credentials, mode 600. Never share.
- `/root/KMJ_SERVER_NEXT_ACTIONS.txt` — public deploy key and safe pending actions.
- `/root/KMJ_SERVER_BOOTSTRAP_STATE` — resumable status.
- `/root/kmj-server-bootstrap.log` — installation/reconciliation log.
- `/home/kmjstage/bin/kmj-stage-deploy.sh` — CI-gated deploy worker.
- `/home/kmjstage/kmj-stage-deploy.log` — deployment log.

## Planned server migration

Before intentionally retiring an old VPS, run:

```bash
sudo bash infra/server/KMJ_SERVER_EXPORT.sh
```

It creates a PostgreSQL custom-format dump, application-managed storage archive when present, a manifest, and a SHA-256 file.

**Copy the export off the VPS.** A backup stored only on the same VPS does not protect against node/provider failure.

## Disaster-recovery follow-up

The bootstrap solves **rebuildability**. Full disaster recovery additionally needs scheduled **off-server** encrypted PostgreSQL/object-storage backups. That should use a provider-independent S3-compatible destination with retention and periodic restore tests. Credentials for that destination must be provisioned as secrets, not committed.

## Acceptance criteria

`KMJ_SERVER_VERIFY.sh` must prove:

- CloudPanel/nginx active.
- PostgreSQL active.
- PHP 8.5 and `pdo_pgsql` present.
- Node 22 and Rust present.
- systemd deploy timer enabled/active.
- deployment source is `staging-approved`.
- local live commit equals `origin/staging-approved`.
- HTTPS returns 2xx/3xx.
- staging `robots.txt` contains `Disallow: /`.

No `PASS` claim is valid when any verification item fails.
