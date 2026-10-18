# KMJ Main Platform Disaster Recovery

## Goal

The VPS is never the source of truth. A complete recovery must be possible on a replacement host using Git plus encrypted off-site business-data backups.

## Backup contract

`scripts/backup_platform.sh` captures:

- PostgreSQL authority data using `pg_dump --format=custom`.
- Laravel application-generated files under `apps/platform/storage/app`.
- UTC timestamp, source host, backup tier, and deployed Git SHA.
- SHA-256 checksums for every unencrypted payload component.

The bundle is encrypted with `age` before `rclone` uploads it. The script fails closed if the database URL, remote target, encryption recipient, required tools, or application storage are missing.

Required runtime inputs are secrets/configuration and must never be committed:

- `BACKUP_DATABASE_URL`
- `BACKUP_REMOTE`
- `BACKUP_AGE_RECIPIENT`
- optional `BACKUP_TIER` (`daily`, `weekly`, or `monthly`)
- optional `APP_ROOT`

## Recommended schedule and retention

Run backups from the VPS or an isolated backup worker with read access to the staging/production database and storage.

- Daily: at least once every 24 hours, retain 14 copies.
- Weekly: retain 8 copies.
- Monthly: retain 12 copies.

Remote object-storage lifecycle rules should enforce retention. Keep at least one remote copy in a provider/location independent from the application VPS.

## Non-destructive verification

Download one encrypted object to an isolated machine and run:

```bash
BACKUP_AGE_IDENTITY=/secure/path/identity.txt \
  bash scripts/verify_backup_bundle.sh /secure/path/backup.tar.gz.age
```

The verifier decrypts into a temporary directory, verifies SHA-256 checksums, checks that PostgreSQL can read the archive with `pg_restore --list`, and confirms the storage tarball is readable. It never connects to or modifies a live database.

## Release schema compatibility QA (not a backup restore)

Before approving a new app SHA, the GitHub `Disposable PostgreSQL Release Gate`
runs the exact candidate in a fresh, loopback-disabled Unix-socket-only PostgreSQL
cluster. The optional `KMJ_PG_FULL_FEATURE_SUITE=1` mode first builds the actual
Vite manifest, then runs the complete Laravel Feature suite against PostgreSQL,
checks KSLP/payment tables and verifies `migrate:rollback`. It never connects
to production or imports real customer data.

A successful full PostgreSQL test **does not** replace the independent drill
of restoring a fresh real encrypted offsite production bundle into a
quarantined disposable recovery host. Also confirm owner-signed release SHA,
correct current production pointer, authenticated owner browser smoke,
outbound email acceptance and rollback before any cutover.
## Replacement VPS recovery

1. Provision and harden a replacement VPS.
2. Clone `kmjtechno/kmj-main-platform` and checkout the exact approved commit required for recovery.
3. Install the platform runtime and PostgreSQL client/server versions compatible with the backup.
4. Configure fresh environment secrets; never recover secrets from Git.
5. Download the chosen encrypted backup from the off-site remote.
6. Verify the bundle with `scripts/verify_backup_bundle.sh` before restore.
7. Decrypt/extract the verified bundle in an isolated directory.
8. Restore `database.dump` into a newly created empty recovery database with `pg_restore`.
9. Restore `storage.tar.gz` into the application storage path and verify ownership/permissions.
10. Run Laravel migrations only after the restored database is healthy and the target commit is confirmed.
11. Run application health checks and the Organization -> Product -> Entitlement -> license validation/revocation smoke path.
12. Switch traffic only under the normal production/DNS owner-approval gate.

## Recovery evidence

For every restore drill record: backup object name, backup timestamp, source Git SHA, target Git SHA, checksum verification result, database archive verification, storage verification, restore duration, smoke-test result, and operator/date. Never record passwords, private keys, database URLs, or decrypted backup contents.

## Activation boundary

Repository tooling and non-destructive verification may evolve through normal engineering PRs. Enabling/changing production backup credentials, storage providers, production timers, DNS, or destructive restore actions requires the applicable owner approval and operational change control.
