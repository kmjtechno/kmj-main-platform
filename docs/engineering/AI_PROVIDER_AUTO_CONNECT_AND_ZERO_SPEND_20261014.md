# AI Provider Login and Zero-Spend Auto Configuration — KMJ CodeBridge

**Design reviewed 14 Oct 2026.** **Status: PR candidates, not deployed.**

## What the user gets after successful authorization

1. In Main Platform → KMJ CodeBridge → AI Providers, choose **Connect OpenRouter**.
2. OpenRouter itself may offer Google, GitHub or another supported identity provider to sign in; this is **OpenRouter authorization**, not blanket Google Gemini/Claude/OpenAI API authorization.
3. OpenRouter returns a short-lived authorization code. Main Platform exchanges it server-side with a single-use PKCE S256 verifier stored in the authenticated session, scoped to the current KMJ organization. The API key is encrypted at rest and never shown in browser props.
4. Read-only model discovery runs; **only discovered IDs ending exactly in `:free`** are configured as initial model and up to five fallback models. No prompts or billed generation are sent by onboarding. If free models or healthy connection are unavailable, display the actual blocked state.
5. CodeBridge/ModelFabric execution is a **separate authorization**: real token quotas, provider privacy/data rules, and CodeBridge scoped execution leases must be checked before using any model. Provider login is not proof that autonomous work has started.

## Google Gemini direct API authorization

Google account authentication and Google Gemini API authorization are separate. Google's official Gemini API OAuth guide requires a Google Cloud project, enabled Generative Language API, configured OAuth consent, a registered Google OAuth client, approved scopes and suitable server credential custody. A CloudOS customer merely pressing "Sign in with Google" **cannot silently create credentials, grant model data scopes, switch AI subscription billing or make all models free**. Direct Gemini OAuth is a future registered-client integration with signed scopes/refresh/revocation and per-tenant consent; otherwise use an owner-created Gemini API key in the encrypted provider manager.

Official docs: https://ai.google.dev/gemini-api/docs/oauth and https://developers.google.com/identity/protocols/oauth2/.

## Provider capability status

| Provider | User-facing connection | Automatic setup after authorization | Cost policy |
|---|---|---|---|
| OpenRouter | PKCE S256; optionally sign in at OpenRouter with Google/GitHub | Encrypted API key + model discovery + verified-free default/fallback only (PR under review) | Hard-block all non-`:free` |
| Google Gemini direct | Google Cloud API key; future owner-registered OAuth consent | Key-based verified model discovery already exists; standalone direct OAuth not ready | Strict owner-maintained free-model allowlist only |
| Groq/Cerebras/Mistral/SambaNova/HF-compatible | Provider-issued key (where supported) | Endpoint probe/discovery after key entered | Deny inference until verified-free allowlist configured |
| Anthropic / OpenAI API | Authorized API credential (not consumer subscription cookie) | Independent API adapter and billing policy needed | No auto-paid fallback; no scraping consumer login |
| KMJ P720 local | Approved CodeBridge local device pairing | Model readiness check using trusted scope | No paid model API, but hardware/electricity costs remain |

## Security gates before release

- Canonical HTTPS `APP_URL` decides the callback origin, not request Host/Forwarded headers; explicit HTTPS + no credentials or query in config, no string-rewrite of arbitrary HTTP callback.
- Authorization code and verifier are single-use; no credential, code or verifier in HTML, logs, database provider listing or redirect diagnostic messages.
- Organization-owner-only connect, recently password-confirmed start, existing session binding and cross-tenant callback isolation.
- No provider successful-status display if model discovery fails or if no free model is usable.
- Auto fallback never includes paid model IDs; limit free fallbacks to five, preserve disabled/blocked routing on failed health checks.
- Do not infer unlimited free quotas/available billing credits from `GET /models`. No cross-service OAuth token reuse.
- Mandatory exact-head `php_tests`, `php_phpstan`, `php_pint`, browser/HTTPS production proxy smoke and provider consent test. Staging app `APP_URL` must be set to its correct publicly reachable HTTPS origin.

**Current status:** Main Platform PR #410 has CircleCI source gates green at its head; GitHub Actions jobs fail before actual steps. This independent follow-up branch changes the OAuth callback and model auto-selection behavior; **its own exact-head checks remain unverified until run**. No live sign-in, paid inference, CloudOS VM, DNS or credentials altered.
