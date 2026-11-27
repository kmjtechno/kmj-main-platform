# Phase 7 redirect map — DRAFT (2026-11-27)

Status: DRAFT, nothing here is implemented or approved. Every row is TO CONFIRM by the owner.
No redirect is added to the application by this document.

## Rules to confirm
- Only permanent (301) redirects for URLs that were publicly live and have a clear successor.
- No redirect from an authenticated/operator route to a public page.
- No redirect chains (A→B→C); each source maps straight to its final target.
- Redirects are tested (status, target, no loop) before any release claim.

## Map (fill in from the live sitemap and Search Console)
| Old URL | New URL | Reason | Owner decision |
|---|---|---|---|
| TO CONFIRM | TO CONFIRM | TO CONFIRM | pending |

## Method to fill it
1. Export live public URLs from the sitemap and the owner's search console.
2. Diff against current public routes (`php artisan route:list`, public group only).
3. For each URL that no longer resolves, propose one successor or a 410.
4. Owner approves rows; implementation is a separate small PR with route tests.
