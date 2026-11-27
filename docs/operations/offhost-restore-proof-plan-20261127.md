# Off-host restore proof and PITR plan (2026-11-27)

Status: `PLANNED`. Nothing here is installed or proven. Roadmap section 17.3 forbids RPO/RTO claims until a restore drill proves them.

## What is proven today (evidence in `work/qa/kmj-receipts/`)
- V3 local guard PASS on 2026-11-26 (manual) and 2026-11-27 08:01 IST (systemd one-shot): fresh pg dump TOC readable, storage manifest, local cipher matches sidecar.
- Vault sidecar check PASS: 54/54 cipher SHA-256 match (receipt 20261126T140107Z).
- Restore drill PASS and storage check PASS 9/9 on snapshot `20261126T133036Z` (same host).

## What is NOT proven
- Restore on a different host or account (`INDEPENDENT_REMOTE_RESTORE=NOT_VERIFIED`).
- Any copy outside this server (`OFFSITE_UPLOAD=NOT_ATTEMPTED_LOCAL_ONLY`).
- Decrypt with the offline recipient key; `recipientVerified`.
- Point-in-time recovery: daily `pg_dump` can only restore to the dump moment.
- The 15:45 IST calendar timer (first scheduled run 2026-11-27).

## Step order (each step small, owner-approved where it touches the server)
1. Owner supplies a throwaway restore target (a second VPS or local VM) and the recipient key custody decision. Claude never holds the private key.
2. Copy one vault snapshot to the target (owner-run, checksum-guarded one-liner), decrypt there, `pg_restore` into an empty PostgreSQL 18, run a row-count and schema comparison, record a receipt without data contents.
3. Record measured restore time. Only then may documents state an RTO for that scenario.
4. PITR: evaluate WAL archiving with pgBackRest, WAL-G or Barman. Tool maintenance status MUST be verified from the project's own repository and releases before choosing; a single blog claim about one tool's sponsorship is not evidence. Needs a server install, so owner approval first.
5. Retention (16 candidate daily snapshots): no deletion until step 2 passes and the owner approves a count.

## Hard rules
No secrets in repo or chat, no paid service, no production data on a laptop without owner consent, and no "production ready" wording from this document.
