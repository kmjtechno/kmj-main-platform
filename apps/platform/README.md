# KMJ TECHNO Main Platform (Laravel application)

The Laravel + Inertia/React application for the KMJ TECHNO Main Platform: accounts, entitlements, licensing, releases/downloads, the KMJ CodeBridge customer dashboard and governed automation.

Repository-level rules (scope, read order, quality gates, theme and release gates) live in the repository root: `CLAUDE.md`, `THEME_LOCK.md` and `RELEASE_GATE.md`.

## Local checks

```bash
npm ci --ignore-scripts
composer install
npm run check   # Vite+ format/lint, source contracts, public layout
```

## Branding

Canonical KMJ assets live in `public/assets/brand/`. `public/favicon.ico`, `public/favicon.svg` and `public/apple-touch-icon.png` are derived from them; `scripts/check-brand-assets.test.mjs` fails if a framework/default icon returns.

Provenance of the original scaffold is recorded in `UPSTREAM.md`.
