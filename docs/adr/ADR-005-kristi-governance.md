# ADR-005: Kristi Governance and Risk Tiers

Status: Accepted

## Decision
Kristi operates through a closed loop:

`Intent/Planner -> Approved Context -> Policy Gate -> Executor -> Independent Verifier -> Audit/Notifier`

## Risk tiers
- Tier A — reversible: may run autonomously under policy and audit.
- Tier B — guarded internal: allowed within bounded tests and rollback rules.
- Tier C — public or financial: prepare complete diff/action, then named human approval is required.
- Tier D — destructive or critical: diagnose/stage only; owner plus second control/break-glass is required.

Kristi is an accountable operator, not an unrestricted superuser. Every tool invocation must be attributable, scoped and auditable.
