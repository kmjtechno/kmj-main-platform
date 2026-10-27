# Prompt-first product creation

Goal: owner enters one public short description; one action generates name, category, offering type and all bounded text content, saves a private planned draft, then opens the actual populated editor. Eliminate the blank duplicate manual form. Existing image upload and GEO/SEO remain; actual cloud image generation is explicitly unconfigured, never simulated. No new dependency, migration, paid or local inference.

Use current Laravel generator with a separate strict brief schema and existing zero-cost guards. Required facts-backed features/FAQs and a substantive bounded description; never invent capabilities or commercial readiness. Request UUID receipts make retries idempotent; changed brief with same UUID conflicts. Explicit publishing/commerce remains unchanged.

Tasks: test-first owner/validation, prompt identity extraction and idempotent save; confirm hosted regression failures; implement controller+generator+prompt UI+populated editor; test real-browser synthetic response rendering and input preservation; full CI and independent review; merge, staging promotion, then reviewed hash-pinned root updater. Real owner live prompt workflow still requires staging verification.
