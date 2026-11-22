# ModelFabric provider and quota-aware routing (2026-11-22)

Status: source-only candidate. No owner credentials connected, cloud prompts sent, migrations run, services restarted or signed production release performed by this change.

## Scope

- Added key-connect presets: Cohere evaluation, Alibaba Qwen Singapore, Alibaba Qwen US and Fireworks AI.
- Existing presets remain: Groq, OpenRouter, Gemini, Cerebras, Mistral, SambaNova, Hugging Face, NVIDIA NIM, GitHub Models, Together, OpenAI and custom HTTPS.
- A preset is **not** a connected provider, approved price, available model, remaining balance, or permission to send private source. Every key must be supplied by its authorized owner and tested independently. Provider credentials never belong in GitHub or UI source.
- Cohere `allowlist` has no default model IDs and is inert unless an owner configures explicit approved free model IDs and required evidence. Qwen and Fireworks presets use `free_tier=none` so they can be connected for discovery without any inference/admission. Never treat trial credits as permanent free usage.
- The existing gateway still admits only `ModelFabricRouter` verified-free eligible routes and re-checks `ProviderManager::assertInferenceAllowed` before sending any model request. No paid fallback, account rotation or quota evasion.

## Quota-aware model failover

- The gateway already classifies jobs into simple/coding/complex and preserves the scoring, owner priority, daily cap, circuit-breaker and bounded 3 actual provider attempts.
- Groq publishes per-model rate limits. On a Groq model returning HTTP 429 with a parseable `x-ratelimit-remaining-requests: 0` response, only that provider/model pair receives a short cooldown (up to 300 seconds, honoring bounded Retry-After). The next already verified-free model on the same provider can run; cooldown on one model cannot unlock paid models.
- If the provider response does **not** report model quota remaining at zero, use the existing conservative **provider-wide** cooldown. OpenRouter remains provider/account-scoped because free models can share account RPM/RPD quotas. Other providers remain provider-scoped until reliable API documentation and contract tests justify a narrower scope.
- Provider/model-specific observed remaining quota feeds the existing scorer so a depleted Groq model is deprioritized independently of other Groq models. This is **not** an account-verified quota reset time or a guarantee that a second model will answer.
- Owner-wide daily caps, credit-limited hard caps, per-token admission, no-training evidence for private source and full secret/endpoint protection are unchanged. If no compliant model is available the gateway fails closed rather than using a paid model.

## References and limits

- Groq per-model developer limits and Retry-After: https://console.groq.com/docs/rate-limits
- OpenRouter shared free models/quotas: https://openrouter.ai/pricing and https://openrouter.ai/blog/llm-api-rate-limits/
- Cohere OpenAI compatibility base URL: https://docs.cohere.com/docs/compatibility-api
- Cohere evaluation keys are limited: https://docs.cohere.com/v2/docs/cohere-faqs
- Qwen regional OpenAI-compatible base URLs: https://help.aliyun.com/en/model-studio/base-url
- Fireworks inference endpoint: https://docs.fireworks.ai/

## Activation requirements

1. Owner connects each provider with the provider's genuine credentials and confirms its applicable terms and private-data handling.
2. Independently verify the exact model's current no-charge price and account-specific hard billing stop; do not infer that an available/free-labelled model can never bill.
3. Run exact-head PHPUnit/Node CI and CODEOWNER review; merge through protected branch.
4. Perform signed release and staging/browser/API verification from **KMJ-elite only**. Compare the protected expected-current release with the actual live release before any production cutover.
5. Execute a consented, non-private route probe only after verified-zero admission, observing a real 429 model fallback receipt and confirming no paid route was used.

No external provider registration or credential minting is automated by this PR.
