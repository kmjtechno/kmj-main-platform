# Backup retention — proposal for owner decision (2026-11-26)

Status: PROPOSAL ONLY. Nothing is deleted, no timer is changed, no policy is approved.
The CodeBridge inventory reports `policyApproved: false` and `deletionAuthorized: false`.

## Observed (read-only inventory, 2026-11-26)
- Daily snapshots: 49 timestamped directories, all with a valid dump, newest 3.3 h old.
- Owner-key vault: 48 cipher+sidecar pairs, no orphans, newest 1.2 h old.
- The inventory's own preview keeps 34 and lists 15 daily directories / 14 cipher pairs as candidates (oldest 2026-10-11).

## Proposed policy (owner to accept, change or reject)
1. Keep the newest 14 daily snapshots and 14 vault pairs.
2. Keep one snapshot per ISO week for 8 weeks.
3. Keep one snapshot per month for 6 months.
4. Never delete the newest snapshot that has a recorded restore PASS (drill receipt).
5. Deletion runs only from an owner-run root script that prints the exact list first and requires an explicit confirm string; no timer deletes anything until the owner approves that separately.
6. Before the first deletion the owner holds a second copy of the owner-key private key and `kmj-backup-age.txt`.

## Not decided here
Disk budget (869 GB free at last read), offsite copy, and whether the V3 Google-pinned vault pairs (not owner-decryptable) are kept or retired.
