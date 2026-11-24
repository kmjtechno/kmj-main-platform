# V3 local backup — restore notes (KMJ-elite)

Scope: the local-only V3 backup (`kmj-v3-dual-local-health.service`, daily 15:45 IST).
Google VPS offsite is **not** a dependency. Written from the 2026-11-24 restore drill.

## What exists
- Daily snapshot (plain, root-only): `/var/backups/kmj-elite-daily/<stamp>/` with `platform.dump`, `SHA256SUMS`, `platform-storage/`, `config/`.
- Vault (age X25519 encrypted pair): `/var/backups/kmj-elite-offsite-encrypted/<stamp>.tar.age` + sidecar sha. Decrypting needs the **owner's private key**, which is not on the server.

## Proven (2026-11-24, snapshot 20261124T063422Z)
Checksum match, `pg_restore --list` (471 entries), full restore of 67 tables into a disposable scratch database, scratch database dropped. Production database and backups untouched.

## Not proven
Decrypting the vault `.tar.age` with the owner key, restoring `platform-storage/`, any snapshot other than the one drilled, and a restore on a different host.

## Version trap (PG16 server, PG18 dump)
`platform.dump` is written by `pg_dump` 18 (archive format 1.16). On this host:
1. `/usr/bin/pg_restore` is 16.15 and fails with `unsupported version (1.16)`. Use `/usr/lib/postgresql/18/bin/pg_restore`.
2. The PG16 server rejects `SET transaction_timeout = 0;`. Convert to SQL and drop only that line:

```bash
/usr/lib/postgresql/18/bin/pg_restore --no-owner --no-privileges -f - platform.dump \
  | sed '/^SET transaction_timeout = 0;$/d' \
  | runuser -u postgres -- psql -X -q -v ON_ERROR_STOP=1 -d <EMPTY_TARGET_DB>
```

Never restore into the production database name. Always create an empty scratch database first and verify there.
Do not make `platform.dump` world-readable; feed it to `postgres` through stdin as root.
