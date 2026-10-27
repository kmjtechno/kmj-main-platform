# Product Workspace Implementation Plan

> Native execution; user explicitly requested continuous implementation.

Goal: restore title-led product drafting, content editing and photo/banner workflow in the locked owner shell.
Architecture: extend the existing governed Product record and manager; generation returns an unsaved review draft. Reuse PublicSeo, sitemap, robots and llms.txt; do not import legacy SEO. Only explicitly configured local Ollama and Stable Diffusion engines; no paid API, synthetic AI fallback or external credentials.
Tech stack: Laravel, PostgreSQL, React/Inertia, existing owner shell.
Spec: current user instructions and inspected public_html.zip service/content/image flow.

Constraints: preserve owner + verified + recent-confirmation gates; generated drafts never publish or enable commerce; no production mutations. Existing artwork unchanged unless owner saves a replacement.
Review focus: unauthorized generation; provider unavailability; invalid/oversized media; content persistence and public escaping; navigation/deep-link behavior.

1. Add HTTP tests for owner-only drafts, disabled engines, validated JSON output, safe media and full content persistence.
2. Extend Product with nullable content JSON. Add local-only draft/media services, validated owner routes and safe public media serving. Run PHP feature/quality CI.
3. Add shared content editor for new/edit products, unsaved generation review, photo/banner upload/preview and discoverable Add Product deep-link. Reuse existing SEO values automatically. Run frontend check/types/build and responsive browser tests.
4. Review exact branch, resolve findings, merge only green CI, prepare schema-aware staging deployment with rollback. Preserve production pointer.
