# One-click catalog research — 27 October 2026

## Scope and observed gap
Screened 13 relevant public repositories using current repository metadata; read candidate READMEs and selected implementation/schema/provider source at pinned commits. This is a targeted survey, not an exhaustive audit of every public GitHub repository. No candidate was installed, benchmarked locally, or used for a live generation request during this research.

The owner screenshot shows the new calibration-enterprise entry saved privately, catalog count 16, and a success result. The workflow is nevertheless incomplete for the requested experience: the separate manual form remains blank; output is generic/short; actual photo and banner are absent. QuickProductCreator stores its result in local created state and refreshes inventory, while CommercialProductForm owns an independent empty useForm instance. The generation contract permits empty feature/FAQ arrays. The image adapter is intentionally unconfigured. A framework import alone will not repair those state and orchestration gaps.

## Candidate evaluation

| Repository | License / state observed | Useful part | Decision |
|---|---|---|---|
| prism-php/prism | MIT; maintained | Laravel provider abstraction; typed structured output and OpenRouter adapter | Best optional PHP adapter candidate. Existing Laravel v13.31.0 satisfies the inspected ^13.12.0 requirement. Not needed just to repair field mapping; preserve our independent verified-zero-price and non-stop-completion guards. |
| cognesy/instructor-php | MIT; maintained | Typed extraction and validation of compound fields | Alternative to Prism, not a second simultaneous framework. |
| Vedant04-tech/ai-powered-ecomm-product-description-generator | MIT; very small project | Category YAML templates, schema bounds, title/meta checks and fact-to-copy structure | Adapt narrowly tested patterns. Its 100-point SEO rubric is a project heuristic, not search-engine ranking evidence. It exports but does not publish to a live catalog. |
| motiful/product-shots | MIT | Reference identity anchors, photo/banner layouts and consistent visual sets | Reuse layout/identity ideas. Its default third-party gateway/API keys are not a verified-zero-cost backend. Do not copy its default provider or automatic retry behavior. |
| spatie/schema-org | MIT; maintained | Schema.org builders for Product/Service/FAQ and graphs | Optional validation/builder patterns for the existing metadata pipeline; no replacement SEO engine. |
| bagisto/bagisto | MIT; maintained | Laravel catalog completeness, attribute handling and product-management UX | Reference selective catalog patterns. Replacing our platform introduces unnecessary migrations and commerce scope. |
| PuvaynBalan/ai-listing-generator | No repository license detected by GitHub metadata | Photo-to-listing/category extraction and quality flags | Concept reference only until an explicit reusable license is established; not an automatic code-copy candidate. |
| google-marketing-solutions/description_genius | Apache-2.0; archived 7 Oct 2026 | Ground descriptions in product attributes plus usage material | Reference only: archived and requires a Vertex-enabled Google Cloud project, not a verified-zero-cost drop-in. |
| pollinations/pollinations | MIT | Unified multimodal provider API | Current README requires API keys and Pollen credits. Do not adopt based on outdated anonymous/unlimited-free tutorials. |
| huggingface/diffusers | Apache-2.0 code; model terms separate | Image-generation tooling | Not appropriate to deploy as local Main Platform inference: ADR-004 cloud-only and compute cost remain. |
| mverab/eGEOagents | MIT | Audit/report ideas and citation/visible-content checks | Optional research reference. Do not import ranking guarantees, fabricated social proof, or an alternative SEO runtime. |
| psbagga17/E-GEO | No repository license detected by metadata | Evaluation methodology for factual product rewrites | Research benchmark, not a turnkey CMS or a ranking guarantee. |
| arjun-go-go/mediaforge | MIT; README identifies early development | Staged text/image/quality/review job pipeline | Architecture reference only: third-party fees and FastAPI/Redis/Celery/Milvus stack are excessive for this Laravel task. |

## Pinned sources inspected
- prism-php/prism @ b620af44d948d708c75ad43df04ab19580af724b — https://github.com/prism-php/prism/tree/b620af44d948d708c75ad43df04ab19580af724b
- cognesy/instructor-php @ 70e72d1063ef15183918c33d04330bd0f3f31df1 — https://github.com/cognesy/instructor-php/tree/70e72d1063ef15183918c33d04330bd0f3f31df1
- Vedant04-tech/ai-powered-ecomm-product-description-generator @ bf9eb82b20f27d126780a4787992ae660bb55948 — https://github.com/Vedant04-tech/ai-powered-ecomm-product-description-generator/tree/bf9eb82b20f27d126780a4787992ae660bb55948
- motiful/product-shots @ 063c508b0b7f4db5cda89f10bdf20df25026dfc5 — https://github.com/motiful/product-shots/tree/063c508b0b7f4db5cda89f10bdf20df25026dfc5
- spatie/schema-org @ cad267981c7ca5a070530e724e00118565d96667 — https://github.com/spatie/schema-org/tree/cad267981c7ca5a070530e724e00118565d96667
- mverab/eGEOagents @ 61ae72fd7117a2e36dabb3460bd898a89f51c783 — https://github.com/mverab/eGEOagents/tree/61ae72fd7117a2e36dabb3460bd898a89f51c783
- pollinations/pollinations @ 27634c5c33d49364ee3e0c1cabb831a1e8d18753 — https://github.com/pollinations/pollinations/tree/27634c5c33d49364ee3e0c1cabb831a1e8d18753

Specific code inspected: the product-description generator's src/schema.py, src/validate.py and templates/electronics.yaml; Prism composer.json and src/Providers/OpenRouter/Handlers/Structured.php; product-shots image-generation script/configuration. The schema validator's quality score and output constraints are deterministic application heuristics. Prism structured handling does not replace KMJ's hard cost gate or rejection of token-truncated responses.

## Cloud image feasibility
Cloudflare Workers AI is the most promising investigated cloud-only image candidate: official pricing currently documents 10,000 neurons/day on Workers Free, with operations failing after limits, and FLUX.1 schnell image generation. Paid accounts can incur usage charges over the allocation. Account plan, shared quota, model availability and actual image generation have NOT been verified for KMJ. No automatic upgrade, paid fallback or assumption of unlimited free service is permitted.

Official references:
- https://developers.cloudflare.com/workers-ai/platform/pricing/
- https://developers.cloudflare.com/workers-ai/models/flux-1-schnell/
- https://github.com/pollinations/pollinations
- https://developers.google.com/search/docs/appearance/ai-features

## Recommended implementation direction
Keep Laravel, current cloud text adapter, locked branding and existing GEO/SEO. Implement one orchestrated, resumable workflow rather than another isolated generator panel:

1. Resolve title/type/category against an approved KMJ facts registry and existing catalog; unknown facts are missing data, not permission to invent capabilities.
2. Generate a complete typed payload with category-appropriate sections. Validate informative descriptions, facts-backed features/FAQs, SEO title/description, slug and alt text. Expose missing facts rather than reporting a generic tiny draft as complete.
3. Generate a master illustration through a verified free-tier cloud image route, then produce photo/banner variants with official logo overlays and identity-safe layout. Clearly distinguish illustrative artwork from actual product screenshots or hardware evidence.
4. Reuse the existing GEO/SEO pipeline for canonical URLs, visible-content JSON-LD, social metadata, public sitemap/AI-readable catalog. Do not import legacy ZIP SEO, fake ratings, offers, or vendor SEO-score claims.
5. Persist the validated draft with idempotent job state. Report text/image/metadata/save progress independently; incomplete imagery remains an explicit partial state, with retry only for the missing stage.
6. Hydrate ONE real editor with the saved record and switch it to edit mode. Eliminate the blank duplicate manual form beneath a success card.
7. Keep publishing/availability/commercial decisions explicit. One click creates a complete catalog draft; no automatic release approval or guessed pricing.

## Acceptance evidence required
- Real owner browser: title -> one action -> persisted record -> same editor populated with all actual content and artwork.
- Live text and image generation with actual quota/cost evidence; no mock presented as live.
- Duplicate/retry protection, failed-stage recovery and stale-edit preservation.
- Published Product/Service routes: initial HTML and client metadata agree; structured claims match visible text; stage remains noindex.
- Production activation remains a separate guarded release.

No application, provider configuration, billing setting or production release was changed by this research.
