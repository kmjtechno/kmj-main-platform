# ModelFabric research and roadmap (21 Nov 2026)

Goal from the owner: the best cloud-only, verified-zero model router for complex coding, with as many
providers as possible connected automatically, one-click sign-in where a provider really supports it,
and smart automatic model shifting before limits run out. Rules stay: ADR-004 (no paid or unknown-cost
route, no local LLM, `NO_FREE_ROUTE_AVAILABLE` when nothing qualifies).

## What exists today in Main Platform
- Provider hub (`/services/kmj-codebridge/ai-providers`), OpenRouter PKCE sign-in, read-only discovery.
- `/operator/modelfabric`: price-evidence registry (max 30 days), route planner, failover gateway with
  cooldowns, metadata-only ledger, 6-hourly discovery refresh (PR #944, #946).
- This slice: rule-based task profile (simple / coding / complex), model-family tiers, scorer, pre-emptive
  shift from provider-reported remaining quota, provider retry-after cooldowns, NVIDIA NIM preset.

## Findings
| Area | Finding | Decision |
| --- | --- | --- |
| Routers | LiteLLM: usage/latency/cost strategies, cooldowns after failures, priority fallbacks, context-window pre-checks. RouteLLM: rule-based routing captures much of the saving without training. | Adopt ideas, reimplement. Rule-based first (no extra model call). |
| Coding proxies | Free Claude Code, claude-code-router, claude-code-mux: per-task routing, failover, admin UI. FCC is AGPL-3.0. | Ideas only; never copy AGPL code. |
| FreeLLMAPI | MIT. Per-key RPM/RPD/TPM/TPD tracking, cooldown, health checks, analytics. Also rotates many accounts' keys. | Adopt tracking/cooldown/analytics. Do not rotate accounts to evade limits (provider terms). Do not trust its external signed catalog as price evidence. |
| OAuth | Real one-click: OpenRouter (PKCE, mints a key, no client id). Hugging Face supports OAuth with an `inference-api` scope, public PKCE clients and device code, but billing/free credit is not stated in its OAuth doc. | OpenRouter done. Hugging Face next: needs a registered public OAuth app (owner action) and its free-credit terms read from the Inference Providers docs before it can be verified-zero. |
| Subscription OAuth | Anthropic forbids Free/Pro/Max OAuth tokens in third-party tools (enforced from April 2026). ChatGPT subscription tokens use an undocumented backend. | Rejected: ToS risk and paid subscription = paid route. |
| Key-paste providers | Gemini (AI Studio), Groq, Cerebras, Mistral, NVIDIA NIM, Cohere, etc. issue keys from a console; no OAuth key mint. | "Almost one click": deep link, paste, auto Test connection, auto discovery, auto refresh. |
| Free tiers | Limits and model lists change often; free tiers commonly log or train on prompts. | Evidence expires (30 days). Private source needs documented no-training evidence, plus separate owner consent. |

## Next slices
1. OpenAI-compatible ModelFabric endpoint with a ModelFabric bearer token, for the CodeBridge coding worker.
2. Hugging Face OAuth (after owner registers a public app) and more presets with documented base URLs.
3. Owner-reviewed catalog of free models with evidence URLs and one-click adoption (the owner's click is the attestation).
4. Daily quota ledger per model, context-window pre-checks, sticky sessions, playground, fallback order editor.
5. Benchmark on real tasks (median minutes, P95, retries, failures) before trusting tier hints.

## Sources
- https://github.com/tashfeenahmed/freellmapi (MIT)
- https://docs.litellm.ai/docs/routing
- https://github.com/lm-sys/RouteLLM
- https://openrouter.ai/docs/guides/overview/auth/oauth
- https://huggingface.co/docs/hub/oauth
- https://raw.githubusercontent.com/Gitlawb/zero/main/docs/oauth-subscriptions.md
- https://github.com/cheahjs/free-llm-api-resources and https://github.com/open-free-llm-api/awesome-freellm-apis
