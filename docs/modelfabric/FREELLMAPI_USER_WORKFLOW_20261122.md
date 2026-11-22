# KMJ ModelFabric — FreeLLMAPI-inspired complete user journey

**Source candidate / not production-live.** Reference: [tashfeenahmed/freellmapi](https://github.com/tashfeenahmed/freellmapi) (MIT). UI patterns and the user journey were studied, not copied line-for-line. KMJ retains its owner dashboard, locked branding, tenant-scoped ModelFabric router and independent provider terms.

## One usable end-to-end path

| Step | What a KMJ owner does | Existing protected surface | This slice |
| --- | --- | --- | --- |
| 1 Connect | Use supported OAuth, or paste provider key, with scoped tenant ownership | Provider Connect Hub | New guided link |
| 2 Discover | Test connection and read discovered models (no inference) | Provider manager and cached model catalog | New stage |
| 3 Approve | Review exact model pricing evidence, quota, data-handling; expiry <= 30 days | Operator ModelFabric evidence, rules and daily caps | New stage |
| 4 Credential | Create a limited, expiring API token; copy it once | Hashed-at-rest scoped bearer tokens | New stage |
| 5 Verify & try | Check /models with a typed ModelFabric bearer; explicitly opt into ONE bounded chat request | Existing /api/modelfabric/v1/models and /chat/completions | New Playground tab |
| 6 Observe | Read 24h provider counts, p50/p95 latency, errors, cooldowns | Metadata-only activity tab | Already implemented |

This flow does not enable a provider by merely adding a key: the gateway remains
verified-free-only and continues returning `NO_FREE_ROUTE_AVAILABLE` when no
current, allowed route can answer.

## Security and interaction contracts

- No requests while the Playground renders. Checking a bearer calls only the
  same-origin ModelFabric `GET /api/modelfabric/v1/models`. It is a read-only
  token/eligible-route check, not a cloud inference request.
- A completion only starts after an owner types a ModelFabric bearer, the
  route check succeeds, a prompt (max 1000 characters) is supplied, and an
  explicit prompt-only consent checkbox is checked.
- The browser issues only fixed same-origin URLs, with `redirect: error`,
  `no-store`, `no-referrer`, and a 30-second AbortController. The bearer
  goes in the Authorization header and is not persisted to storage or URL.
  Switching tabs unmounts the card and clears its in-memory token state.
- This consent is **not** authorization to transfer private repositories,
  customer data or credentials. The Playground sends exactly the supplied
  prompt; users must not paste secrets. No provider secrets are exposed to
  the browser. Provider, model and cost eligibility remain server-controlled.
- The caller-supplied model is always the alias `modelfabric-auto`; the
  gateway ignores attempts to name a paid/unverified provider directly.
- No paid fallback, new payment method, provider key rotation, subscription
  OAuth token scraping, zero-cost bypass, headless source-upload, DNS/proxy
  change, production cutover or schema migration.
- The UI's optional route counter and 24h activity are real metadata, **not**
  claims that a coding agent ran, a provider invoice is zero or every
  integration is activated.

## FreeLLMAPI product parity: implemented vs future independent slices

- Already available on KMJ: provider/key/OAuth flows, discovery, model approval,
  custom limits/priority, free route planning/failover, cooldowns, API bearer
  and OpenAI-compatible chat, streaming replay, metadata activity, scoped
  private-source restrictions.
- Implemented here: guided five-stage onboard-and-verify journey, isolated
  non-secret Playground with both non-inference `/models` check and a
  guarded interactive `/chat/completions` test; no new backend privileges.
- Not claimed implemented: 87 provider connectors, FreeLLMAPI external
  premium signed catalog, Fusion multi-model synthesis, media APIs,
  downloadable desktop app, automatic tool-specific CLI configuration, full
  model detail benchmark pages, per-key TPM/TPD counters, prompt compression,
  advanced routing visual editor, video/image/audio interfaces or multilingual
  localization.
- Follow-up candidate features should be scoped and tested individually:
  one-click API client configuration for supported IDEs, tenant-scoped
  fallback-profile editor, per-model/request usage windows, provider-health
  troubleshooting, SDK integration smoke tests and bounded independent
  accounting receipts. Never equate an upstream catalog's "free" label with
  today's owner-attested billable price.

## Acceptance criteria

Run `node --test scripts/check-modelfabric.test.mjs` from `apps/platform`,
then the repository's actual checks/CI on the exact PR head. Smoke in an
authorized staging environment with a test tenant:

1. Anonymous and non-owner browser cannot mint or use owner tokens.
2. Without an API key the Playground button is disabled.
3. With no verified routes, `GET /models` is readable but POST is blocked.
4. Unauthorized/expired token returns 401; no redirect follows a bearer.
5. With a valid, permitted, no-secret prompt and explicit consent, one POST
   routes through the original ModelFabricGateway, or returns a generic
   denied status. No direct upstream host receives the bearer from the UI.
6. No token/prompt persists after tab unmount or in app storage.
7. PHP/Laravel tests plus React/TypeScript/Vite checks pass.
8. A separately approved, signed Elite deployment is verified by actual
   authenticated UI before marking this shipped.

Reference: `docs/modelfabric/MODELFABRIC_RESEARCH_AND_ROADMAP_20261121.md`.
