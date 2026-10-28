# P0 — 91FF staging uploads: lossless migration admission (28 October 2026)

**Source-only advisory, NOT a deployment or authorization.** Target:
`91ff3296597c3901865960d39936816ac9ca4c7a`. The 15:52 UTC
owner operator receipt `KMJ_91FF_STAGE_OPERATOR_RECEIPT_20261028.txt`
(SHA-256 `dc93ad14a842230a0433b61636e0fb2bfd21922a3cb38555d03afdf91c1d2efe`)
says `BLOCKED_UPLOAD_RELEASE_BOUND`; production activation was NOT attempted.
The older staging upload directory resolves inside a disposable release. The
guard is correct: do not remove it, point the new release at the old directory,
move files blindly, or delete the old release.

## Read-only evidence before any migration

The existing owner-reviewed root diagnostic (already staged on KMJ-elite)
`work/qa/KMJ_91FF_STAGE_STORAGE_LAYOUT_DIAG_20261028.sh` has exact SHA-256
`99c4c1d4fba6d04b3b0159497b0dad63e42babfa25a221714c63f3fa5b17fb15`.
Its bounded output is `work/qa/KMJ_91FF_STAGE_STORAGE_LAYOUT_20261028.txt`.
It does not copy, chmod, relink, delete, or reveal file contents. An absent
receipt means **not evaluated**. It reports old resolved upload target, file
count, bytes, symlink count, last-ten-minute writes, release references,
product-artwork target, candidate scaffold, shared destination occupancy,
filesystem identity, and disk availability. These are diagnostics, **not**
an inventory digest or owner-signature proof.

Run the offline evaluator only after reading the exact sanitized diagnostic
through CodeBridge:

```bash
python3 -B scripts/operations/assess_91ff_stage_upload_layout.py \
  work/qa/KMJ_91FF_STAGE_STORAGE_LAYOUT_20261028.txt
```

The evaluator always exits nonzero and returns `stage_switch_authorized=false`;
it cannot silently turn a diagnostic into a release approval.

## Owner-reviewed migration acceptance sequence (not executed)

1. Verify actual current staging and production pointers, source SHA, root
   ownership, immutable candidate, shared artwork target, all symlink references
   and source/destination mounts. Reject drift, unexpected bind mounts,
   symlink loops, mountpoints, hardlinks or out-of-scope paths. Preserve the
   existing old release, DB and current public upload URL behavior.
2. Obtain a **fresh encrypted, verified, independently restored** backup of
   staging uploads and database, including product artwork, with a manifest
   of file types, relative paths, bytes, modes, hashes and link targets.
   Do not copy secrets into GitHub, QA receipts or public build assets.
3. Provision a new persistent **root-verified** shared upload target with
   correct least-privilege ownership and capacity, separate from all
   `/home/kmjstage/releases/*` directories. An occupied target requires
   independent reconciliation, not overwriting. Preserve
   `/home/kmjstage/shared/product-artwork` as its existing canonical target.
4. During a permitted staging-only maintenance window, quiesce ALL writers
   (web requests, queues, cron, image jobs) that can write the old upload
   tree. Confirm quiescence twice. Initial copy may occur before quiescence,
   but final sync and integrity check MUST occur while writes are stopped.
   A ten-minute mtime count of zero alone is **not** proof of quiescence.
5. Use a separately reviewed, owner-approved, hash-pinned migration
   implementation with no `--delete`, no unsafe symlink dereference and
   no cross-filesystem rename assumptions. Copy into a fresh private
   destination, verify full relative-path manifest, hashes, permissions,
   symlink/hardlink semantics, and count/bytes against the frozen source.
   Treat any mismatch or disk exhaustion as a hard stop. Do not remove source.
6. Under a separate owner-approved atomic staging-only transaction, link the
   staging old and candidate storage to the persistent verified target,
   preserve public storage URLs and artwork, and test uploads, downloads,
   owner Product Studio Generate/Edit/Save/Reopen and rollback. On failure
   restore old pointers without deleting either data copy; keep writers
   quiesced until verified recovery.
7. Require fresh exact `X-KMJ-Deploy-SHA` HTTPS evidence, authenticated
   owner QA, candidate-specific encrypted offsite restore and rollback.
   Only then can a **new independently signed** production manifest binding
   real `platform-8070dad72c55` and target SHA be considered. Existing
   `readyToActivate=false` MUST block production activation.

**Never delete production accounts as part of storage migration.** The
25-user audit found 24 other unverified accounts with organization and
reset-token relationships; deletion requires separate recoverable backup
and relationship reconciliation. Do not enable unattended autopublish or
Cloudflare paid inference during this operation.

This source-only PR deliberately does not modify the 91FF staging activation
script, protected approval, staging timer, Nginx, DB, storage, or production.
