# KMJ Main Platform — Strict Release Gate

Deployment is BLOCKED unless every gate below is verified PASS on the exact release candidate.

- BUILD: production frontend build exits 0.
- DIFF: git diff --check exits 0.
- ASSETS: every referenced production asset exists and loads with non-zero dimensions; no duplicate placeholder where a dedicated product asset is required.
- DESKTOP QA: homepage and /products return 200, no horizontal overflow, no browser/page errors, no broken images.
- MOBILE QA: same checks at 390px viewport, including full-page scroll to exercise lazy-loaded assets.
- ADMIN QA: authenticated Platform Owner can open Product Manager; create/edit, lifecycle, show/hide and ordering controls complete without browser errors.
- LIVE SMOKE: after release candidate validation and controlled deployment, / and /products return 200 and core services remain active.

Fail closed: any FAIL, BLOCKED, missing evidence, missing asset, or untested authenticated path means NO DEPLOY.
Evidence must belong to the exact release candidate; never carry PASS status from another commit.
