# KMJ CodeBridge — self-hosted verification without paid CI

**Goal:** verify the exact Device Control Center branch on your own Linux workstation or disposable local CI runner. This script never calls CircleCI, GitHub APIs, Render, KMJ Main Platform production, or a paid AI model.

From a **fresh disposable checkout** of this repository, restore exact locked Node/PHP dependencies once through your approved package cache (or a trusted vendored artifact). The one-time package source may require internet; the actual verification script itself performs no dependency downloads.

```bash
cd apps/platform
bash scripts/verify-codebridge-device-control-offline.sh
```

Safety policy: deliberately refuses existing `.env`, `.env.production` or cached runtime configuration. Runs only with ephemeral `APP_ENV=testing`, SQLite `:memory:`, in-memory mail/queue/cache and randomly generated runtime-only APP_KEY. Generates Wayfinder TS routes with `--with-form` before checking TypeScript; checks three CodeBridge authorization-related PHP source files and enrollment service; then executes focused tenant isolation, credential revocation, enrollment and onboarding tests.

Use this in a standalone local Git worktree, **not a production checkout**. The verification does not modify the production database or device credential store. Linux bash, Node 24+ and installed Composer/vendor+node_modules are prerequisites. This removes dependence on an external CI provider **for executing these checks**, but it does not satisfy all independent release and deployment qualification gates. CircleCI workflow is an optional free mirror, not an authority for commercial deployment.

Separate product context: KMJ CodeBridge itself already supports loopback local `npm run gateway` / `npm run agent` with its free community mode and no third-party CI; a cloud AI chat's model usage and third-party desktop app updates are external services by their nature.
