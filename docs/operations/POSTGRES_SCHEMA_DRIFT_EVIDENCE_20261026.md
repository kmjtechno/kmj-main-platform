# PostgreSQL 18 remains the KMJ primary database

This slice borrows only the schema-drift review concept from Bytebase. It does not install Bytebase, replace PostgreSQL, edit Laravel migrations or open a database dashboard. The Main Platform remains PostgreSQL-based; Laravel is the sole owner of application-schema migrations.

## Now implemented in development source

- A read-only PostgreSQL catalog query in scripts/ci/postgres_schema_metadata.sql inventories public-schema regular/partitioned tables, column names/types/nullability, and constraint names/kinds. No application table rows, function bodies, default expressions, credentials or customer records.
- A bounded, dependency-free offline comparator in scripts/ci/compare_postgres_schema_metadata.py reports added/missing metadata counts without printing object names to public CI logs.
- Real-PostgreSQL fault injection in scripts/ci/verify-postgres-staging.sh creates an extra table **on the existing disposable Unix-socket-only CI database**, verifies that drift is detected (expected exit 1), drops it, then requires a clean restored inventory. Normal Laravel migrations, functional tests and rollback checks still run afterward.
- Offline unit tests cover forged metadata, version mismatch, altered columns, duplicate identifiers and missing constraints.

The actual server major is reported from server_version_num. The existing GitHub disposable PostgreSQL workflow installs the distribution's PostgreSQL version; a PG16 CI run is not proof of PG18 compatibility. Before promoting a production PG18 candidate, run a real PG18 rehearsal and restore with exact-head evidence.

## Operational separation

Compare only two snapshots from separately approved sources. A matching result proves only equality of this **limited metadata scope**. It does not attest source identity, role completeness, table contents, data safety, indexes, triggers, functions, security policies, extensions, sequences, SQL review quality or general production release readiness.

Authorized read-only operator workflow, **not automatically executed**:

1. With an independently verified read-only PostgreSQL role and a trusted local Unix-socket connection, obtain two metadata snapshots from approved environments. Example: psql -X -qAt -v ON_ERROR_STOP=1 -f scripts/ci/postgres_schema_metadata.sql > before.json (repeat using a distinct approved connection/filename). Caller authenticates the endpoint; script never stores credentials.
2. Run: python3 -B scripts/ci/compare_postgres_schema_metadata.py --expected before.json --actual after.json. Exit codes are 0 MATCH, 1 DRIFT or major-version mismatch, 2 BLOCKED_INVALID_SNAPSHOT.
3. Preserve safe evidence separately with trusted timestamps and identities. Never claim real production schema parity without verifying both sources.

Bytebase Community server is **not live**. Running it on the production host adds a new service and access surface; first require version/digest-pinned isolated evaluation, license/feature review, loopback-only exposure and customer-data access review. AI/MCP inspection needs a separately authorized **read-only** role; no superuser, unrestricted SQL tool, paid Enterprise features or untrusted auto-migration.

## Production activation currently blocked

The server release controller must independently report readyToActivate=true for the intended new candidate SHA, with matching current release, protected backup/restore evidence and authenticated owner QA. A source merge is not the customer website going live. Never override the protected approval manifest or current symlink to make a gate pass.

Concept source: https://github.com/bytebase/bytebase
No upstream source code or Enterprise-licensed components copied.
