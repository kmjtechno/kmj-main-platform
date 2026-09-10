# tests/architecture

Architecture tests will enforce repository boundaries before feature volume grows.

Initial assertions:
- Main Platform has no dependency on KMJ Cloud Nexus implementation code.
- Domain modules do not import another module's persistence model.
- Provider adapters are separated from domain authority.
- Entitlement/licensing authority cannot be derived from UI visibility or raw payment webhooks.
- Generative AI policy remains cloud-only, verified-zero and no-paid-fallback.
- Production mutation paths remain owner-approval gated.
