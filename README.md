# KMJ TECHNO Main Platform

KMJ TECHNO Main Platform is the clean-foundation enterprise operating platform for kmjtechno.com and future KMJ products.

## Locked boundaries
- This repository is **not** KMJ Cloud Nexus. Cloud Nexus remains separate and untouched.
- Git is the source of truth.
- Cloud-only generative AI; no local LLM inference.
- Paid AI fallback is prohibited. Unknown cost is not free.
- If no currently verified zero-cost AI route exists, return `NO_FREE_ROUTE_AVAILABLE` and keep deterministic workflows usable.
- One authoritative writer per protected repository/worktree.
- Production publish, DNS, billing, destructive database operations, signing-key operations, and other critical changes require explicit owner approval.

## Bootstrap V1
The first bootstrap provides a stateless controller, mission state, safety gates, GitHub verification workflows, Render blueprint, and one-click start endpoints/scripts. It intentionally does not make an AI call until a verified-zero route is configured.

## First thin vertical slice
`Organization -> Product -> Entitlement -> Signed sandbox license -> Product validation -> Revocation`
