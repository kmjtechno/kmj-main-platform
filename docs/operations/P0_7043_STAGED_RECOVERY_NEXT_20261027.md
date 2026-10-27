# Recovery preparation for staged 7043ac candidate — 27 Oct 2026

**Staged candidate SHA:** `7043ac70051271f61441b5bb7a57ef709193d0bf`.

Operator evidence already supplied: `KMJ_FAST_STAGE=EXISTING_VERIFIED`,
`KMJ_CANDIDATE_SHA=7043ac70051271f61441b5bb7a57ef709193d0bf`,
and `KMJ_PRODUCTION=UNCHANGED`. This verifies one staged isolated
candidate, NOT the current content or SHA served by
`https://staging.kmjtechno.com/`. Separate concurrent work controls
that staging hostname: **do not touch its Nginx, TLS, files or databases**.

The strict non-activating helper
`scripts/operations/prepare-p0-7043ac-local-recovery-20261027.sh`
was derived from the previously reviewed protected local recovery pattern,
with **candidate and current-release identities pinned**. The script is
operator-only, root-only on KMJ-elite; it runs a real local production
PostgreSQL `pg_dump` via the authorized Laravel connection as `kmjprod`,
packages storage, proves SHA-256 integrity, restores the dump to an isolated
local PostgreSQL Unix-socket cluster (TCP explicitly disabled), checks
selected table identities, and writes a root-owned witness. It does not
perform production DB writes, deploy, alter `.env`, approve releases,
touch staging or claim independent offsite backup.

**Privacy restriction:** the locally retained backup bundle contains a
protected copy of the live `.env`; it must stay root-owned mode 0600 and
**must not be pasted here, attached, committed, emailed or uploaded**.
Use the separately reviewed offsite sanitization/encryption process before
any transmission; no offsite copy for this new candidate is established here.

The generated witness is meaningful only after an actual successful
`LOCAL_DISPOSABLE_POSTGRES_RESTORE=PASS` receipt. CI verifies only the
source contract and shell syntax, **not live production backup completion**.

## Release gates remaining after local restore

- Independently sealed/offsite copy and real offsite restore proof for this
  new candidate; never reuse `b1d672...` witness as 7043 approval.
- Snapshot exact staging serving SHA and complete authenticated Owner
  browser QA in coordination with the other chat.
- Candidate rollback rehearsal with its separate signed evidence.
- New protected owner approval for the **actual** live current release
  `platform-8070dad72c55` and the candidate SHA.
- Only when the privileged supervisor responds
  `readyToActivate=true`, run the installed guarded production activation
  and verify actual public readback. No symlink or manifest bypass.

Keep this PR unmerged while the owner is freezing the staged 7043
application candidate if changing `main` would invalidate their
latest-main pin. This is a SHA-pinned *operator recovery aid*, not an
application change that must immediately advance `main`.
