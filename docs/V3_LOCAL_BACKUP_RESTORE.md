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

## Owner-key vault (added 2026-11-24)

The V3 vault (`/var/backups/kmj-elite-offsite-encrypted`) is encrypted to one pinned X25519 key (`age1952vsyz...`, "pinned Google X25519" in the installed V3 encryptor). The owner does not hold its private key (searched the owner PC drives C: and D:; the P520 recipient in `/etc/kmj-p520-restore-trust` is a different key). So that vault is NOT owner-decryptable.

`scripts/kmj-owner-key-backup-vault.sh` (PR #1147) seals the newest checksum-verified daily snapshot to the owner's own age public key into `/var/backups/kmj-owner-vault/<stamp>.tar.age` (+ `.sha256`), no-clobber, deleting nothing.

Proven (2026-11-24, stamp 20261124T145907Z): the ciphertext downloaded to the owner PC matched its sidecar SHA-256, decrypted with the owner's private key, and contained `platform.dump` (705987 bytes, same size the server reported) and `SHA256SUMS`. The `age1chnglg...` private key lives only on the owner PC.

Not proven: a database restore performed from the owner-decrypted copy (the earlier restore drill used the plain local snapshot), any stamp other than the one tested, automatic daily creation (this was a one-time run, no timer), retention, and a restore on a different host. The owner's private key must be kept in at least two separate places.

## Restore drill and timer evidence (2026-11-25)

- Owner-key vault timer installed (PR #1154): `kmj-owner-key-vault.timer`, hourly, first scheduled run 12:04 IST (not yet observed at the time of writing). The installer's own first run sealed stamp 20261125T023402Z.
- Owner PC decrypt, second stamp 20261125T023402Z: sidecar SHA-256 matched, decrypt succeeded, 102 tar entries, `platform.dump` 911913 bytes.
- Disposable restore on the server (PG18 `pg_restore` to SQL, PG16 server, empty scratch DB per stamp, scratch DBs dropped afterwards): `platform.dump` of snapshot 20261124T145907Z and of 20261125T023402Z both restored with `ON_ERROR_STOP=1`, 69 public tables each. Production database untouched.
- The two snapshots come from different jobs: 20261124T145907Z from the V3 helper (schema kmj.local.full.daily.v3, 261 storage files, 329 checksum lines); 20261125T023402Z from the older root backup job (9 storage files, 2 checksum lines, "Not offsite"). Live `storage/app` is about 32K. File-by-file storage completeness of the older job is NOT verified.

Still not proven: row-level data equality with production, restore of the encrypted copy itself on the server (the key never leaves the owner PC), the scheduled timer run, retention, a different host.


## Row-count restore drill (2026-11-26)

`scripts/kmj-backup-restore-rowcount-drill.sh` (PR #1199, volatile-table fix PR #1200, merge `97685ab`) restores the newest checksum-verified daily snapshot into a disposable scratch database, compares per-table row counts with the live database (read-only), drops the scratch database and writes a counts-only receipt to `/var/lib/kmj-restore-drill/`.

- Owner root run on KMJ-elite, snapshot `20261126T023521Z`, script SHA-256 `0d812e0f947b83dd7d47084269683dcd6f64bff752d1388627fae3011ec0524f`: `RESTORE_DRILL=PASS`.
- First run with the earlier script (before PR #1200) gave FAIL only because `sessions` shrank 125 -> 103 (expected expiry). Same restore, 76 of 76 tables on both sides, 65 equal, 10 with higher live counts (new rows since the snapshot), none missing or extra.
- Rule: fail on any missing or extra table and on any non-volatile table where the snapshot has more rows than live. Volatile tables (sessions, cache, cache_locks, jobs, job_batches) are reported, not failed.

Not proven by this drill: row-by-row data equality (counts only, snapshot is older than live), `platform-storage/` file completeness, any other snapshot, retention, a restore on a different host, and mail delivery.
