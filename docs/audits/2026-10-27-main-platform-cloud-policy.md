# Main Platform cloud policy and P520 audit

Scope: recursive repository inventory at 81ca15d2d87fe51e9e64d0fc240822c0b93676f3 (1195 entries), governing ADR/config, product studio, existing Python free-cloud router, owner routes and CI. This is a scoped engineering audit, not an attestation that every source line or all production behavior is defect-free.

Confirmed findings:
- ADR-004 and config/free-cloud-routing.yaml require cloud-only verified-zero inference. PR612 introduced an incompatible dormant local adapter. PR617 replaces it with an official free-cloud product adapter; no local inference or paid fallback.
- Existing Python engineering router remains separate and unchanged. Its identity/allowlist eligibility rules are not treated as sufficient fresh price evidence by the product adapter. The product adapter requires current model catalog zero prices, zero provider price caps and zero reported response cost.
- Existing PublicSeo, canonical metadata, sitemap and llms.txt consume the reviewed public catalog; legacy ZIP SEO remains excluded.
- P520 existing runtime is clean/pinned per owner terminal output. Its private scoped enrollment was not found; current connected account has no P520 grant. Official interactive pairing is necessary; no revocation, credentials copying or grant fabrication. P720 is retired from this work.
- Public cloud drafting submits only owner-entered public product facts. No customer records, repo secrets, credentials or private account metadata are read into prompts.
- No verified-zero cloud image provider is configured; upload stays operational and image AI remains explicitly unavailable.

Official provider references checked 2026-10-27:
https://openrouter.ai/docs/guides/routing/routers/free-router
https://openrouter.ai/docs/api/reference/limits
https://openrouter.ai/docs/guides/routing/provider-selection

Real cloud inference, hidden server-side key setup, P520 account-side heartbeat and staging activation remain separate verification steps. Free quotas are finite; no additional spend is authorized.
