# ADR-007 — Hosting Provider Compliance Guard

Status: Accepted
Date: 2026-09-12
Scope: KMJ TECHNO Main Platform operations and hosting compliance

## Context
KMJ must operate within the active VPS/hosting provider Terms of Service, Acceptable Use Policy, resource limits, abuse rules, email policy, backup obligations and suspension conditions.

The platform must reduce avoidable suspension risk without giving automation unrestricted legal, billing, DNS or destructive authority.

## Decision
Build a provider-neutral Hosting Provider Compliance Guard inside the governed Operations/Operator Console.

Core flow:

`Provider Policy -> Versioned Snapshot -> Approved Rules -> VPS Telemetry -> Compliance Evaluation -> Safe Mitigation -> Evidence/Alert`

The system is preventive and evidence-driven. It does not claim that suspension can be made impossible.

## Policy source model
For each hosting provider store approved source URLs and metadata for:
- Terms of Service
- Acceptable Use Policy
- resource/CPU/RAM/IO limits
- bandwidth/network rules
- email/spam/abuse policy
- prohibited workloads/content/services
- backup/retention responsibilities
- incident/suspension/termination rules

## Policy monitoring
- capture a timestamped/hash-addressed snapshot when permitted
- detect material policy changes by normalized diff
- keep machine rules separate from raw legal text
- require human approval before a new/changed legal clause becomes an enforcement rule
- preserve source URL, retrieval time, reviewer and effective version

AI may summarize a changed clause, but AI output is not legal authority.

## Telemetry and compliance signals
Monitor provider-relevant operational signals such as:
- CPU, memory, load, disk and inode pressure
- process and worker concurrency
- queue depth and retry storms
- bandwidth and connection anomalies
- mail volume/bounces/complaints when available
- failed authentication and abuse indicators
- storage growth, log growth and backup age
- exposed service/port inventory where permitted

Every signal must have provenance and freshness metadata.

## Safe automated mitigation
Low-risk reversible actions may be automated after policy approval:
- throttle/pause non-critical workers
- reduce safe queue concurrency
- slow non-essential outbound mail
- rotate/prune disposable logs within retention policy
- pause optional background tasks
- apply temporary upload/request limits
- notify the owner/operator with evidence

## Approval-gated actions
Automation must not independently:
- accept/reject legal terms
- alter provider billing/subscriptions
- change production DNS
- delete authoritative customer/business data
- rotate or reveal privileged credentials
- respond to legal notices as final authority
- disable security controls merely to reduce resource use

Those actions require owner approval and audit evidence.

## Provider neutrality
Provider-specific collectors and policy parsers sit behind adapters.
The business platform must not depend on one hosting provider's proprietary API.

## Reliability requirements
- fail closed when a policy/rule is unknown or stale
- never fabricate a provider restriction
- keep last-known-good approved policy version
- alert when monitoring itself is stale/unavailable
- every automatic mitigation must be reversible where practical
- keep before/after evidence and correlation IDs

## Delivery priority
Implement incrementally without blocking the Revenue MVP:
1. provider profile + source registry
2. policy snapshot/diff service
3. VPS resource telemetry and thresholds
4. compliance dashboard + alerts
5. approved safe auto-mitigation
6. provider API adapters when justified

## Non-goals
- guaranteeing a provider can never suspend service
- automatic legal interpretation
- unrestricted infrastructure control
- creating a second source of business truth outside Main Platform
