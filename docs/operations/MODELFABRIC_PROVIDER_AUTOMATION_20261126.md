# Native ModelFabric provider onboarding and zero-cost automation

Research snapshot: 26 November 2026. FreeLLMAPI is an architectural reference, not a runtime, catalog subscription, or proxy dependency. Its upstream README reports 87 provider adapters and 1,313 free endpoints, but its own architecture documentation describes a single-user experimental service and warns about upstream terms and unavailable production guarantees. KMJ must independently qualify account, model, API scope, commercial use, quota, privacy and pricing.

## Connection priority

| Provider | Official authentication | Admission |
| --- | --- | --- |
| OpenRouter | Existing native authorization-code PKCE exchange | Exact zero-price free routes; strict private coding additionally needs account admission and documented privacy |
| Gemini | API key now; documented Google OAuth requires an OAuth client, project and quota binding | Free-tier public/non-sensitive workload only until data handling and billing verified |
| Groq | API key | Existing owner-verified free allowlist; verify free plan and per-model limits |
| Mistral | API key | Free mode; exact account and model qualification |
| SambaNova | API key | Free plan; verify model and account limits |
| Cloudflare Workers AI | Scoped token and account ID | Separate account-bound adapter; free-plan quota and model restrictions |
| Z.ai, SiliconFlow, ModelScope, AnyAPI | API key/token | Discovery-only presets in this change; no inference |
| NVIDIA NIM, Cohere | API key | Evaluation constraints; no assumption of production eligibility |
| Hugging Face | Existing OAuth authorization-code PKCE | Free accounts currently lack included inference credits; keep zero-cost qualification mandatory |
| Pollinations | Documented BYOP PKCE/device flow | Requires registered app key and user balance; defer until no-charge budget proof |
| Puter | User authorization | User-pays is not a zero-charge guarantee; defer |
| Cerebras | API key | Credit trial, not ongoing free capacity |
| OpenCode Console | API key | Its free chat routes are restricted to OpenCode itself; do not work around restriction |
| GitHub Models | Retired 30 July 2026 | Historical records only; no credential probe or inference |

## Automated workflow

1. Start only official provider authorization (state, PKCE and owner/tenant binding). Never scrape credentials from a browser or treat social sign-in as an inference grant.
2. Encrypt credentials at rest. GET models is discovery only; do not send a prompt for discovery.
3. Apply unexpired, narrow owner rules immediately after a successful recheck; scheduled refresh already runs every six hours. Revocation, stale discovery, or an organization mismatch must prevent rule admission.
4. Independently validate exact input/output price, quota, permitted use and data handling. Unknown or exhausted evidence denies inference. A free account, visible catalog or a trial credit alone is not sufficient.
5. Keep a separate stricter private-source coding gate, including request-bound native admission, source consent and no paid/local fallback.
6. Next: add an independent signed KMJ catalog with source URLs and expiry, automatic account-specific quota checks, bounded background rechecks, and a provider capability/terms review queue. Implement OAuth for additional providers only when official delegated API authorization and zero-charge proof are available. Credentials and account consent remain owner-only.

## Proactive quota rotation (owner policy, 26 November 2026)

- Prefer eligible routes with headroom over sticky sessions and owner priority; retain task fit inside each headroom group.
- At 80% of a configured KMJ daily cap, prefer another admitted route. The existing cap remains a hard ceiling enforced by database reservations, including ambiguous failures.
- Groq documents the request limit, remaining requests and request reset headers as RPD, distinct from minute-level token limits. For its exact API host, retain validated model-specific daily headroom until the reported reset, shift at 80% utilization and skip a reported zero balance until reset. Respect shared organization and project constraints; do not create or rotate accounts to evade provider limits.
- Unknown or malformed reset data is not daily quota evidence. Other providers keep their existing conservative short-lived signals and owner caps until their account-specific quota semantics are independently verified.
- No paid or unknown-cost route is admitted by this change. Cached provider observations are advisory except a verified zero quota; concurrent/external usage can change upstream availability. No actual account quota, live inference or authenticated production acceptance is claimed.

## Primary sources

- https://github.com/tashfeenahmed/freellmapi
- https://github.com/tashfeenahmed/freellmapi/blob/main/docs/en/architecture/00-high-level-index.md
- https://openrouter.ai/docs/api/api-reference/o-auth/exchange-auth-code-for-api-key
- https://openrouter.ai/pricing
- https://ai.google.dev/gemini-api/docs/oauth
- https://ai.google.dev/gemini-api/docs/pricing
- https://console.groq.com/docs/rate-limits
- https://cloud.sambanova.ai/plans
- https://mistral.ai/pricing/
- https://developers.cloudflare.com/workers-ai/platform/pricing/
- https://huggingface.co/docs/inference-providers/main/pricing
- https://gen.pollinations.ai/docs
- https://docs.puter.com/user-pays-model/
- https://www.cerebras.ai/pricing
- https://docs.github.com/en/github-models
- https://opencode.ai/docs/console/api/inference/
- https://zcode.z.ai/en/docs/configuration
- https://www.siliconflow.com/
- https://github.com/modelscope/hermes-modelscope-api
- https://anyapi.ai/pricing

No live account or inference verification is claimed by this research or source change.

## OAuth provider qualification and canonical workspace (26 November)

- Existing OpenRouter PKCE and Hugging Face delegated inference authorization are retained. Owner legacy provider GET resolves to the canonical ModelFabric workspace; non-platform organization users retain their scoped page.
- Pollinations documents app registration and PKCE at https://gen.pollinations.ai/docs and https://github.com/pollinations/pollinations/blob/main/BRING_YOUR_OWN_POLLEN.md. Its user-authorized keys can spend a wallet budget. Do not advertise it as a working free router until a registered app, authenticated key validation, exact zero-price admission and non-billable request proof exist.
- Google Gemini OAuth requires a connected Cloud project; API-key setup remains the verified implementation. Do not request broad cloud permissions or silently enable billing. See https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/migrate/migrate-google-ai and https://ai.google.dev/gemini-api/docs/pricing.
- Do not use private CLI/session tokens, browser cookies, or retired GitHub Models to inflate OAuth counts. Account authorization is separate from model free-tier admission and private-source consent.

## 26 November: keyless free quota research and screenshot audit

- Kilo Gateway documents anonymous `:free` inference and 200 requests/hour per IP shared across authenticated and anonymous calls: https://kilo.ai/docs/gateway/authentication and https://kilo.ai/docs/gateway/usage-and-billing. Exact free suffix only, no key, no paid fallback, no private-source route, no NVIDIA trial prefix; explicit owner public-only opt-in. Live catalog, inference, commercial model-specific terms and shared quota behavior still require acceptance. Respect upstream 429; never rotate accounts/IPs to bypass limits.
- OpenRouter free variants: 20 RPM, 50 RPD without qualifying purchased credits, account-wide; https://openrouter.ai/collections/free-models/. Do not purchase credits for ModelFabric. Groq published limits and model headers: https://console.groq.com/docs/rate-limits. Google account/project limits and pricing: https://ai.google.dev/gemini-api/docs/pricing. Mistral Free mode is account-specific: https://docs.mistral.ai/admin/billing-usage/usage-limits/.
- Cloudflare Workers AI: 10,000 neurons/day on Workers Free, paid plan can bill overage and some models are paid-only; https://developers.cloudflare.com/workers-ai/platform/pricing/. Add a distinct account/plan-aware adapter rather than treating neurons as requests. Latest HF pricing lists no monthly free-user inference credits (older docs conflict); https://huggingface.co/docs/inference-providers/main/pricing. Do not assume old $0.10 allowance.
- Pollinations BYOP needs registered app and wallet budget; Google Gemini OAuth needs registered Cloud client and quota project. Neither is an existing operational free OAuth route. FreeLLMAPI has many API-key providers, not equivalent to many delegated OAuth integrations.
- Existing credit-limited route reservation is per model/request/day, not a verified account-wide monetary cap. Do not approve a paid-capable model using this alone; require provider-enforced no-overage or a shared account budget ledger with conservative maximum request cost, reset/expiry and external usage reconciliation. Preserve private-source consent and exact no-training evidence.

### 26 November qualification follow-up

- Kilo local rolling-hour count spans all organization rows using this preset; PostgreSQL transaction advisory lock serializes reservations, and local 429 cooldown is shared. Prefer other eligible routes at 160/200 attempts. This is a conservative local count, not authoritative IP usage: external requests, deleted history and upstream availability can affect actual headroom. Upstream 429 remains authoritative. Exclude NVIDIA/Nemotron trial identifiers and reject non-empty key or mismatched endpoint.
- OVHcloud Olala-v1.0-mini-7A1B is explicitly listed Free: https://www.ovhcloud.com/en-gb/public-cloud/ai-endpoints/catalog/olala-v1-0-mini-7a1b/. Anonymous quota is documented, but the free API page describes playground/testing: https://www.ovhcloud.com/en-sg/public-cloud/free-ai-api/. Verify production entitlement before admitting it.
- LLM7 currently documents a required API token and free-token limits of 100,000 tokens/day, 250 requests/hour, 60/min, 1/sec; not keyless. https://llm7.io/privacy and https://llm7.io/compare/claude-sonnet-4-6--vs--gpt-5-4/. Verify no paid overage and downstream use terms before admitting.

### Quota visibility and expanded discovery directory

- The owner workspace now exposes local shared Kilo rolling-hour attempts and cooling state (not upstream remaining balance), local configured UTC-day request caps, and provider-reported rate counters separately. Model-admitted does not mean an inference probe has succeeded.
- LLM7 and Pollinations OpenAI-compatible endpoints are discovery-only until their account-specific free/no-overage eligibility is independently verified. Pollinations model listing is public but generation requires a scoped key; PKCE app registration alone does not make inference free. https://gen.pollinations.ai/docs; https://llm7.io/privacy.
- OpenCode Console free-tier chat explicitly restricts external clients (HTTP 403); do not imitate its client or bypass the gate. https://opencode.ai/docs/console/api/inference/. Kilo Auto Free can select NVIDIA trial endpoints, so do not include that alias in commercial routing. https://kilo.ai/docs/gateway/models-and-providers.

### Shared credit-limited connection cap

For credit-limited inference the gateway now counts all UTC-day attempts for a provider connection and applies the lowest current credit-limited evidence cap across its models. Near-cap prioritization and reservation-time recheck use the same conservative cap; missing/invalid hard-cap attestation fails closed. This is a local request ceiling, not a monetary ledger or a verified account-wide balance across multiple keys or external clients. A provider-enforced hard no-overage policy and account-specific verification remain mandatory. Do not add more credit-based routes merely because their catalog is readable.

### Automatic refresh admission integrity

The existing scheduled catalog refresh runs every six hours; current owner-scoped narrow model rules can admit newly discovered eligible IDs without a separate approval for every model. Explicit manual evidence (even expired) and credit-limited evidence cannot be rewritten into a free rule approval. On allowlist providers an explicit expired or revoked per-connection evidence row overrides a global environment allowlist default. Tests cover both precedence failures. This preserves the zero-cost guard when free-model catalogs change; new free provider rules still require accurate pricing and account eligibility evidence.

### Explicit public-prompt scope

Kilo anonymous routing requires per-request public-data confirmation. Ordinary API tokens are not sufficient. The OpenAI-compatible endpoint accepts `X-ModelFabric-Public-Prompts: confirmed` only as a caller assertion that the payload contains public, non-confidential data. Private-source and strict-coding scopes always exclude keyless routes even when the header is supplied. The safe playground sends this header for catalog preview and for its explicitly consented synthetic prompt; mail and other internal callers default to no keyless routing. Kilo's upstream anonymous and authenticated free traffic shares 200 requests/hour per IP (https://kilo.ai/docs/gateway/authentication; https://kilo.ai/docs/gateway/usage-and-billing). Live upstream inference still requires acceptance.
