# ADR-003: Commercial Authority Chain

Status: Accepted

## Decision
The authoritative chain is:

`Account -> Organization -> Subscription -> Entitlement -> License -> Device Activation`

## Invariants
- Payment state is not a license.
- Commercial agreement comes from the order/subscription ledger, not a raw payment webhook.
- Capability comes from entitlement policy, not UI visibility.
- Device rights come from the license/activation ledger, not an editable local file.
- Trusted releases come from signed artifact/provenance records, not filenames or download URLs.
- Public claims come only from approved catalog/content facts.

Subscription, entitlement and licensing transitions that affect rights are recorded in append-only audit/ledger records.
