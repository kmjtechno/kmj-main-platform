# KMJ TECHNO — Production release blocker audit (read-only, 27 October 2026)

**Active owner coordination:** Another ChatGPT conversation currently owns
`https://staging.kmjtechno.com/`. Do not alter staging releases, database,
vhost, TLS, DNS, catalog, deployment, source tree or services from this lane.
Home Office **P520 and P720 are intentionally offline** and must not be
paired, awakened, restarted, enrolled or included as a release dependency.

## Exact current evidence (not an activation)

- Public production currently resolves to `platform-8070dad72c55`.
- Protected previous approval expects `platform-54142f844c0b`, so the fixed
  CodeBridge supervisor reports `readyToActivate=false`. Both Nginx and
  PHP-FPM are active. No manual approval rewrite or symlink cutover is allowed.
- Current GitHub main (as of authoring this issue) is
  `7043ac70051271f61441b5bb7a57ef709193d0bf`; re-fetch main before
  every candidate build. Any source PR merged afterward requires a **new**
  exact-SHA candidate and matching tests. Earlier B74C/69AC backup receipts
  cannot authorize this newer SHA.
- Anonymous staging homepage HTTPS was reachable with `noindex,nofollow`,
  **but staging acceptance is managed by the other chat**.
- PR #597 initial raw HTML SEO metadata and PR #599 owner-approved expiry-only
  CodeBridge credential remediation are merged into source, **not verified live**.

## Zero-write audit command — operator on KMJ-elite ONLY

From a fresh, verified, current checkout, the owner/operator may run:

```bash
python3 -B scripts/operations/audit-production-release-blockers-readonly.py \
  --inspect 7043ac70051271f61441b5bb7a57ef709193d0bf
```

That SHA is illustrative of the **27 Oct main at authoring time**, not a
permanent pin; operator must substitute the actual exact current main SHA.
The audit enforces root + host identity, fixed safe path boundaries, reads
only the current release pointer, exact candidate Git head/clean state,
build-artifact existence, protected approval fields, SHA256-backed local
backup/witness and health of Nginx/PHP. It does **not** read or output private
environment values or credentials. Invalid host/arguments block before any
production inspection.

`APPROVAL=PROTECTED_EXPECTED_CURRENT_RELEASE_MISMATCH` means a new
protected release approval is needed; don't change the old file to make
the audit green. A `BACKUP=LOCAL_SHA256_WITNESS_PASS` means only that
the **candidate-matching local file** matches its SHA256 witness—not that
the backup was restorable. A backup flag is not proof of restoration.
This read-only program **never** claims release authorization and never
starts the release systemd unit.

## Remaining independent gates

1. Build exact **current main** in a separate immutable
   `/home/kmjprod/releases/platform-<sha12>` using the already-reviewed
   source-only candidate builder and local operator access. Preserve dirty
   working checkout, untracked owner files, current release and staging.
2. Verify a **new** candidate-matching protected backup/witness, independently
   download/decrypt and restore offsite archive on an isolated host, and
   old/new/old HTTP+database recovery. Real independent restore evidence must
   be in the approval, not merely a true JSON flag.
3. Conduct real authenticated owner Super Admin browser QA, protected owner
   authorization, customer denial, catalog mutations only inside disposable
   staging/test DB, payment/license guard and locked visual acceptance.
   Coordinate with the other staging chat—don't overwrite its candidate.
4. Only then create a new owner-protected manifest referencing the
   independently verified candidate SHA and **actual** current production
   release; confirm supervisor `readyToActivate=true` and use its fixed
   guarded activation. Never force a symlink, override flags or bypass gates.
5. Verify the exact post-activation release SHA, production `/`, `/products`,
   `/login`, raw HTML SEO/meta, private noindex, CodeBridge server readiness,
   Nginx/PHP and rollback readiness. **P520/P720 remain offline by design**.

## Run deterministic tests without a VPS

```bash
python3 -B -m unittest discover -s scripts \
  -p test_production_release_readonly_audit.py -v
```

No extra paid API, worker process, third-party service, Windows connection,
database write, Cloudflare DNS change or remote deployment is introduced.
