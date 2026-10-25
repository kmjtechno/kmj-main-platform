# KMJ TECHNO: One public domain, fast guarded releases

**Canonical public production:** https://kmjtechno.com/ only. Do not present
staging.kmjtechno.com as a second customer website or treat its response as proof
that a candidate has deployed.

## 25 October 2026 live evidence

- \`/home/kmjprod/current\` resolves to \`platform-8070dad72c55\`.
- Existing SHA-pinned candidate \`b1d672bbc83a51ca3f8271435692825072444c8e\` is staged.
- The root-owned backup + witness for **that candidate** passed independent SHA-256 verification.
  This is **not** a backup/rollback approval for any newer SHA.
- \`staging.kmjtechno.com\` has a DNS-only A record to the same server,
  but no staging-specific Nginx vhost, no CloudPanel CLI, and TLS fails with
  curl exit 60. A browser redirect to the main site is not staging acceptance.
- The protected production activation manifest expects the *older*
  \`platform-54142f844c0b\` pointer. Actual live is different. Supervisor
  \`readyToActivate=false\`. **Do not edit the current symlink or overwrite
  the approval manifest to make this check green.**
- \`main\` has advanced beyond the older candidate. A verified candidate must
  be built from the exact newly approved main commit.

## Fastest safe pipeline without a public staging hostname

1. Integrate feature branches through code review and complete exact-commit
   GitHub CI, isolated Laravel/PostgreSQL testing, and Windows/browser QA
   appropriate for the release. Reject unrun or failed tests.
2. On KMJ-elite, stage the *current exact main SHA* in a **new isolated**
   \`/home/kmjprod/releases/platform-<sha12>\` using
   \`scripts/operations/stage-fast-main-candidate-no-activation.sh <40-SHA>\`.
   It refuses stale main commits, unexpected host, dirty/changed checkout,
   present candidate .env, missing build artifacts and release-lock contention.
   It never modifies the live site, shared development checkout, production
   credentials, Nginx, database, DNS, or release approval.
3. Have the authorized operator verify **that SHA's** real database/storage
   backup, independent disposable restore, migrations and rollback rehearsal.
   Do not transfer credit from the older b1d672 archive. Prepare only the
   candidate's protected runtime configuration after independently checking
   the canonical public agent origin and private gateway.
4. Operator validates customer routes, owner-only login and authorization,
   subscriptions/license integrity, release provenance and the candidate
   against the locked approved visual reference in isolated QA. Physical
   calibration tests remain separate.
5. After explicit protected approval for exact SHA and **actual** current
   release, the installed CodeBridge supervisor must report
   \`readyToActivate=true\`. Only then use its fixed guarded
   \`supervisor_main_platform_production_activate\` operation. No arbitrary
   SSH deploy, symlink overwrite, forced manifest update, insecure TLS or
   CloudPanel CLI assumption.
6. Immediately verify https://kmjtechno.com/ (public and authenticated owner
   routes, enrollment, real assets, payments/licensing guards), exact deployed
   SHA, Nginx/PHP health and rollback receipt. On failure use the fixed
   verified rollback procedure.

## What changes now, and what does not

- **Use GitHub Actions and isolated local QA as the release acceptance lane**.
  A public staging TLS certificate is **not** a prerequisite for the new
  candidate builder; the broken staging subdomain should not be part of any
  new customer-facing deployment journey.
- **Do not blindly disable/delete the staging DNS record or bypass existing
  staging workflows.** Existing workflows explicitly depend on it, so
  retire or rewire those workflows under a separate verified migration first.
- Main Platform source being merged does **not** make it live. Automated
  build/promotion is appropriate; unattended production deployment is allowed
  only after all protected candidate, backup, authenticated QA and rollback
  gates are verifiably satisfied.
- Device re-enrollment should occur **once** after the corrected public origin
  is live and trusted. Do not reuse deleted credentials, show or share pairing
  codes/tokens, or label an unauthenticated HTTP 422 as device READY.
