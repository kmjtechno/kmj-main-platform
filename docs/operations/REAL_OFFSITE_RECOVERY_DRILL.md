# KMJ Main Platform — real encrypted offsite restore evidence

**Status: source-side operator tool. Actual production backup has NOT been restored or independently verified in this chat.**

Synthetic PostgreSQL backup and archive-signature checks cannot prove an actual production backup can be recovered. The script at scripts/operations/verify-real-offsite-recovery.sh is a strictly guarded operator-run drill for a **separate recovery host**, not a deployment procedure.

## Preconditions

- A non-root account on an independent disposable recovery host. It needs at least **12 GiB free on its persistent recovery scratch filesystem**, and larger real backups may need much more. Refuses the known KMJ-elite production hostnames. A cloud `/tmp` often has less than 12 GiB because it is RAM-backed and must not be used.
- Installed PostgreSQL server/client binaries, age, rclone and Python, and a preconfigured existing backup remote.
- Private age identity installed securely on the recovery host; do not paste its contents or any rclone token into chat, issues or CI.
- Confirm the existing backup remote's download fees and approved egress budget first. Some remote storage providers bill for retrieval: **zero additional cost is not automatic**.
- Do not use placeholder remote values or point this at live production PostgreSQL.

## Persistent scratch preflight

Prepare a private, non-symlink directory under the logged-in recovery user's home (NOT on KMJ-elite). On Google VPS this is `/home/info/kmj-recovery-scratch` and lives on the persistent root filesystem:

    install -d -m 700 "$HOME/kmj-recovery-scratch"

The operator script checks ownership, exactly 0700 permissions, same filesystem as the user's home, and at least 12 GiB free. Both its private PostgreSQL restore and the nested checksum/archive verifier use this directory by exporting `TMPDIR`. They clean up only their own randomly named temporary directories on exit. No existing home or recovery-vault files are deleted. Make sure the backup plus its temporary decrypted/extracted copies will fit comfortably beyond the 12 GiB minimum.

## Operator invocation

Set KMJ_ACK_ISOLATED_RECOVERY to YES, BACKUP_REMOTE_OBJECT to the *actual existing configured rclone remote object* (remote:path/to/file.age), and BACKUP_AGE_IDENTITY to the private identity file path, then run:

    bash scripts/operations/verify-real-offsite-recovery.sh

The script downloads the caller-selected remote object, verifies the encrypted bundle with the existing bounded archive validator, decrypts to a private temporary directory, restores to an empty PostgreSQL database in a new local Unix-socket-only cluster, checks recovered public.users, public.organizations and public.entitlements tables, and extracts recovered storage into a private folder. It always tears down the disposable cluster and removes temporary decrypted files. There are no production database connections, remote deletions, DNS changes, merchant transactions or deployment commands.

## Evidence and limitations

- OFFSITE_RETRIEVAL=PASS: chosen existing rclone path was actually read; independently witness that the remote is off the production VPS.
- BACKUP_ARCHIVE_INTEGRITY=PASS: encrypted archive decrypted and passed checksum/member verification.
- DISPOSABLE_POSTGRES_RESTORE=PASS: the real snapshot restored successfully to a brand-new isolated PostgreSQL DB.
- RECOVERED_APP_SCHEMA=PASS / RECOVERED_STORAGE=PASS: minimum business-schema and storage presence checks.

**Remaining gates:** complete recovered app functional smoke with tenant/org/license state, owner-authenticated locked screenshot signoff, real sender/inbox receipt and signed link, merchant webhook/settlement, matched immutable deployment approval, current production pointer and rollback proof. The operator script deliberately prints SAFE_TO_ACTIVATE_PRODUCTION=NOT_PROVEN, never a false production PASS.

Archive verification and syntax/negative tests in GitHub CI are not execution against a real backup. Preserve UTC operator receipts and exact release SHA without exposing remote names, raw records or credentials.
