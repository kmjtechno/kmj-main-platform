# Bytebase evaluation and KMJ migration safeguards (26 Oct 2026)

**Implementation status:** GitHub PR/CI-only static risk audit and migration immutability check. This is not Bytebase installed, not a live database console, and not a production release. Zero paid cost and zero database network calls.

## Adopted now

- **Database-as-code and PR review:** versioned Laravel migrations remain owned exclusively by the Main Platform release pipeline. New migration files receive independent, best-effort risky-pattern checks and existing migration files are immutable across PRs.
- **SQL review risk signals:** flag destructive schema/table/column changes, raw database statements, foreign-key-guard bypass and other changes that require deliberate review. These are coarse lexical signals, **not** Bytebase's SQL AST review rules, not a comprehensive proof of SQL safety, and not an authorization system.
- **Audit/evidence:** one GitHub check with exact head SHA and deterministic minimal findings. SQL content, secrets, database rows and credentials are not printed.
- **No redundant migration runner:** the existing disposable PostgreSQL release gate already executes new Laravel migrations on an isolated local PostgreSQL cluster, selected feature tests, and a rollback check. It remains the functional acceptance gate. This new workflow adds static review only.

## Deferred, not silently switched on

- **Bytebase Community Docker/server:** first evaluate off-production, pinned image digest, localhost-only port, no production DB credential, independent data backup, and a dedicated low-privilege development PostgreSQL database. No installation is attempted in this PR.
- **Bytebase GitOps and SQL review integration:** configure only after checking community-tier feature entitlements and ownership. The Laravel release process remains the sole application-schema writer; Bytebase may be used as a review/inspection tool, never a second independent production migrator.
- **Bytebase MCP read-only:** OAuth grants inherit a Bytebase user's privileges. Do not attach owner/admin credentials to CodeBridge. If deployed later, provision a dedicated read-only DB role plus explicit access limits, redact sensitive columns at source and verify review/audit behavior with negative tests. No new MCP endpoint is exposed here.
- **Schema drift:** needs separately attested live environment snapshot with approved metadata-only visibility; a list of migration filenames is **not** database schema drift verification.
- **Enterprise-only features:** do not copy restricted enterprise or licensing code or represent them as free.

## Actual release criteria

1. Exact-head GitHub workflow and disposable PostgreSQL release gate PASS; separately prove SQL-parser quality if claiming comprehensive linting.
2. Operator verifies dedicated encrypted, recoverable backup and isolated restore/rollback for the intended production SHA (not a previous candidate).
3. Staging/current release SHA, protected approval, Main Platform owner-authenticated browser QA, payment/license and gateway controls PASS.
4. A guarded operator-installed release operation executes and reports actual live SHA. A source merge alone is **not** a deployment.

Sources: https://github.com/bytebase/bytebase and https://docs.bytebase.com/integrations/mcp. No upstream code was copied.
