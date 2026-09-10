# ADR-004: Cloud-Only Verified-Zero Generative AI

Status: Accepted

## Decision
Generative AI inference is cloud-only. Local LLM inference is prohibited. A model route is eligible only when current explicit evidence shows zero price for the planned use.

## Invariants
- Unknown cost is not free.
- Trial credits and ambiguous marketing language do not qualify as verified-zero.
- Paid fallback is prohibited.
- If no eligible route exists, return `NO_FREE_ROUTE_AVAILABLE`.
- Deterministic build/test/git/IDE workflows must remain usable without an AI route.
- Routes require concurrency limits, bounded retries, circuit breakers and periodic re-validation.
- Prompts must minimize/redact secrets and unnecessary personal data.

Provider-specific code must live behind adapters so free-route churn does not infect domain logic.
