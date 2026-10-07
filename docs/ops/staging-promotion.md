# Staging Promotion Policy

## Purpose

The private repository is currently on a GitHub plan where native ruleset enforcement is not available for this private repository. Therefore, the staging environment must not deploy directly from `main`.

## Canonical staging source

The VPS must deploy only from the branch:

`staging-approved`

`main` remains the development integration branch. `staging-approved` is a machine-maintained promotion ref and must not be used as a development branch.

## Promotion rule

`.github/workflows/staging-promotion-gate.yml` runs on every push to `main` and performs the complete staging gate:

1. controller compilation;
2. locked runtime invariants;
3. architecture foundation checks;
4. versioned contract verification;
5. module architecture verification;
6. runtime provenance verification;
7. PHP 8.5 setup;
8. Node 22 setup;
9. deterministic SQLite CI database preparation;
10. platform install/build;
11. platform lint/type/static-analysis/test checks.

Only when every gate succeeds may GitHub Actions move `staging-approved` forward to the exact verified `main` SHA.

The promotion uses a non-force Git ref update. A history rewrite or non-fast-forward condition fails closed instead of silently moving the staging ref.

## VPS rule

The staging VPS deploy worker must fetch and deploy `staging-approved`, never raw `main`. The server-local systemd timer is the deployment authority; GitHub Actions verifies convergence rather than opening an inbound deployment session.

Expected flow:

`main -> Staging Promotion Gate -> staging-approved -> VPS auto-deploy timer -> staging-only exact-SHA header -> HTTP/UI/browser verification`

## Failure behavior

If any verification step fails:

- `staging-approved` does not move;
- the currently working staging deployment remains live;
- the VPS auto-deploy timer does not receive the failed `main` commit;
- no paid AI fallback, production action, DNS action, or destructive action is implied.

## Security boundary

This gate reduces accidental or unverified staging deployment risk, but it is not a substitute for native protected-branch enforcement. When the account plan supports enforcement for this private repository, native branch protection/rulesets remain required.

Production `kmjtechno.com` is outside this workflow and remains owner-approval gated.
