# packages/contracts

Versioned external and cross-module contracts live here.

Planned contract families:
- OpenAPI schemas for Identity, Catalog, Entitlements, Licensing and Releases.
- CloudEvents-compatible event envelopes.
- Shared identifiers and error/status codes.

Rules:
- Contracts are versioned before consumers depend on them.
- Breaking changes require explicit migration/versioning.
- Product clients never receive database persistence models as API contracts.
