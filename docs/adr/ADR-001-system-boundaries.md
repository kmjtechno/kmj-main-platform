# ADR-001: System Boundaries

Status: Accepted

## Decision
KMJ TECHNO Main Platform is the central business/product/customer/licensing/release/automation system. KMJ Cloud Nexus remains a separate engineering IDE and is not part of this repository. Kristi is a governed operating layer that may interact through approved APIs/tools; it is not an unrestricted superuser or shared-database shortcut.

## Consequences
- Main Platform and Cloud Nexus must not share persistence models or silently bypass contracts.
- Product clients consume versioned APIs/contracts, never direct database access.
- Cloud Nexus integration, when introduced later, must be versioned and explicitly scoped.
- This repository must remain independently buildable and testable without Cloud Nexus.
