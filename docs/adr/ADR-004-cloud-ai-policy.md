# ADR-004: Zero-Spend Generative AI (free, credit-limited and owner-operated local)

Status: Accepted. Revision 2, owner-directed on 2026-11-22. Revision 1 was "cloud-only verified-zero".

## Decision
Generative AI inference may use three route classes. All three keep the owner's cash spend at zero.

1. **Free-tier cloud routes.** Eligible only when current explicit evidence shows zero price for the planned use
   (unchanged from revision 1).
2. **Credit-limited cloud routes (new).** Free credits or a fixed free allowance that runs out. See "Credit-limited rules".
3. **Owner-operated local or self-hosted routes (new; revision 1 prohibited local inference).** See "Local route rules".

A paid fallback stays prohibited. If no eligible route exists, return `NO_FREE_ROUTE_AVAILABLE`.

## Credit-limited rules
A credit-limited route is eligible only when current evidence shows all of these:
- The provider cannot bill the owner beyond the granted credits: no payment method on file, or a prepaid/hard cap
  that makes overage impossible. A card on file with pay-as-you-go overage is NOT eligible.
- Exhaustion stops service instead of charging. KMJ also keeps its own usage counter and daily/monthly cap per route,
  deprioritises at 80% and skips at 100%, so a mis-stated provider limit cannot spend money.
- The credit amount and expiry (or the allowance reset period) are stated by the provider, and the evidence URL is kept.
- Evidence expires within 30 days and is revocable, exactly like free-tier evidence.
- Ambiguous marketing language, "trial" wording without a stated cap, and unknown billing behaviour do not qualify.

## Local route rules
A local route runs a model on infrastructure the owner operates (for example an OpenAI-compatible server such as
llama.cpp, vLLM or Ollama). It has no per-token fee, so it is zero-spend for the owner's cash, but it must satisfy:
- The endpoint is registered by the platform owner. It is never a tenant-, customer- or request-supplied URL, so the
  existing SSRF protections stay in force for every other provider.
- Host and port are pinned in owner-controlled configuration. No redirects, no arbitrary hosts.
- It must not degrade production serving. Local inference runs on a separate device or a resource-limited unit unless
  the owner explicitly approves co-location on the production server.
- Concurrency, timeout and token limits are enforced like any other route.
- The model licence must permit the planned use, and the licence note is kept as evidence.
- Because prompts stay on owner infrastructure, a local route may be approved for private source code when the owner
  approves it explicitly; cloud routes still need their own no-training evidence for that.

## Invariants
- Unknown cost is not free.
- Paid fallback is prohibited.
- If no eligible route exists, return `NO_FREE_ROUTE_AVAILABLE`.
- Deterministic build/test/git/IDE workflows must remain usable without an AI route.
- Routes require concurrency limits, bounded retries, circuit breakers and periodic re-validation.
- Every route class is admitted by the same planner. Failover and scoring can reorder admitted routes but never add one.
- Prompts must minimize/redact secrets and unnecessary personal data.

Provider-specific code must live behind adapters so free-route churn does not infect domain logic.

## Implementation status (honest)
This revision changes policy. Current code admits free-tier cloud routes only (allowlist, `:free` suffix). Credit-limited
routes and owner-registered local endpoints need their own reviewed slices (evidence fields, usage counters, a pinned
local-endpoint registry). Until they ship, routing is unchanged and still fails closed. Older documents that say
"no local LLM" (README, master roadmap, workflow summaries, UI copy) are superseded by this ADR and are updated as
those slices land; `CLAUDE.md` is owner-maintained.

## Revision history
- Rev 1: cloud-only verified-zero; local inference prohibited; trial credits did not qualify.
- Rev 2 (2026-11-22, owner): add credit-limited cloud routes under hard-cap rules; allow owner-operated local routes.
