# KMJ Main Platform: npm build versus production-runtime dependency boundary

**18 November 2026 — source review, NOT a production release approval.**

The React/Inertia frontend is compiled into static assets by Vite. Its TypeScript, Tailwind compilation, compiler plugins and Vite CLI are **build tools**, not Node services running in PHP-FPM production. The historical `package.json` incorrectly categorized several of them as production `dependencies`, causing `npm audit --omit=dev` to include vulnerable picomatch paths through Vite and laravel-vite-plugin.

This branch reclassifies **11 top-level build tools** as `devDependencies` and regenerates the npm v3 lockfile's production/dev flags **without changing any version or integrity pin**. The two picomatch versions stay in the full locked build toolchain; they are NOT renamed, deleted or replaced with a fictitious fixed version. The repository script `apps/platform/scripts/check-runtime-dependency-boundary.mjs` walks the production-plus-optional dependency graph and fails if picomatch becomes reachable as a production dependency. Both the standard `npm audit --omit=dev --audit-level=high` and the full bundle build and PHP checks must still execute.

## Security scope, explicitly not waived

The current advisory **GHSA-fc5q-39xc-vjpf / CVE-2026-112366** affects picomatch through 4.0.7, including the locked compiler version, and has **no verified upstream fixed release** as of this review. Reclassification can correct a **production runtime** vulnerability report but DOES NOT fix or suppress the **build-time** vulnerability. No engineer should mark the full Node install clean or report a fix for the upstream code.

- Full build dependency exposure must remain visible to reviewers. Run `npm audit --audit-level=high` (all dependencies) and document its advisory result; it is **expected to fail** pending a trusted upstream fix or a separately approved, regression-tested and pinned alternative.
- Build/test workers must not evaluate customer-controlled globs or application-controlled untrusted patterns. A build-worker risk assessment and genuinely fixed package remain a release/security acceptance requirement, not a reason to silently ignore an audit.
- Lockfile metadata must be generated/verified reproducibly. No `npm audit fix --force`, no audit ignore list, no arbitrary remote tarballs, no invented patch version, no fake clean SBOM.
- Frontend assets must be built inside a protected isolated lane; customer production must not require `node_modules`, `vite` or Node package installation at request-serving runtime.
- This change does not authorize payment, license signing, customer issuance, KSLP rollout, root commands, DNS changes or production activation.

## Independent release blockers (untouched)

- Protected production manifest still expects `platform-e5b43872bc03` while live is `platform-ce6ad7dc9d89`; staging approval is invalid. Do not replace protected values with user-written JSON. The owner must authorize a freshly reviewed candidate pinned to the actual current release.
- Offsite backup unit and fresh local archives are present and last exited 0, but no independent physical P520 encrypted readback, PostgreSQL+uploads restore and signed rollback evidence has passed.
- Stacked Licensing Hub workflow PRs #892, #894, #895, #896 and #897 are drafts, not merged or authorized for commercial release. AuthSP archives are user-journey references ONLY, never code or secrets to deploy.

**Acceptance:** exact-head `npm ci` reproducibility, runtime boundary proof, production runtime audit, full build advisory evidence, isolated Laravel/PHP and Rust/JS tests, independent recovery, owner-signed CE6-based staging/production gate. A green runtime-only audit is not a claim of overall release readiness.
