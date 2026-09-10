# ADR-002: Modular Monolith with Event-Driven Seams

Status: Accepted

## Decision
The Main Platform starts as a modular monolith. Each domain owns its data, service interface, authorization rules, events, tests and migrations. Cross-module writes go through explicit interfaces or events.

## Initial modules
Identity & Access, Organizations, Catalog, Commerce, Entitlements, Licensing, Releases, Content & Growth, Support & Trust, Automation & Audit, Public Experience, Customer/Org Portal, Developer/Partner Portal, Operator Console, Kristi Operations.

## Integration rules
- OpenAPI for external APIs.
- Versioned CloudEvents-compatible events for asynchronous integration.
- Transactional outbox for durable event publication.
- Idempotent consumers with deduplication.
- No direct import of another module's persistence model.

Microservices are deferred until measured operational or scaling evidence justifies extraction.
