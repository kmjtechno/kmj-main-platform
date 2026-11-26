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
