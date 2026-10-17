# Locked KMJ visual verification

This preview imports the real landing page, operator dashboard, CSS and public assets. Its Inertia props are explicitly synthetic: preview catalog, zero orders and no credentials. It is not an authenticated Laravel route or a production build.

From `apps/platform`, with Node 22.12+:

```sh
npm ci
npm run visual:install
npm run visual:build
npm run visual:verify
```

The verifier starts and closes a fixed loopback Vite server, opens landing and operator at 1536, 768 and 390 pixels, tests image loading, overflow, JavaScript errors, section order, Kristi guidance and command search, and writes six PNGs plus `visual-results/verification.json`. For manual review use `npm run visual:dev`. A preinstalled Chromium can be selected with `KMJ_CHROMIUM_EXECUTABLE`; the default uses Playwright's installed browser. `KMJ_SCREENSHOT_DIR` changes the output directory. These are local developer configuration, not remote tool arguments.

## CodeBridge integration boundary

The audited CodeBridge connection has no callable browser/screenshot tool. This repository now supplies a deterministic command suitable for a dedicated administrator-defined `main_platform_visual_ci` profile: run `npm run visual:verify` in the approved isolated checkout's `apps/platform`, with dependencies/browser preinstalled, a 180-second timeout and bounded PNG/JSON artifact collection. Do not accept arbitrary URLs, shell fragments, credential paths or environment overrides from remote tool callers. The runner accepts loopback only and never invokes deployment or Laravel authentication.

Installing that command profile into the running CodeBridge gateway is still required; adding these scripts does not activate a remote capability. Do not claim CodeBridge browser verification until its profile has executed against the exact candidate SHA.

## Production release gates

Run the ordinary PHP/Laravel build, TypeScript and project checks independently. Run authenticated owner smoke tests for existing governed product/order actions in an approved test environment. Preview success does not establish authentication, database correctness, permission enforcement or deployment readiness. Do not ship `visual/` or `.visual-preview/` as public Laravel routes.

The artwork is recreated WebP, not an exact source-image extraction. Runtime products and monetary values come from existing server props; never insert the mock's invented financial values. The homepage overview-video modal currently explains that a video is unavailable.
