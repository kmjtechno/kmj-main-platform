# KMJ TECHNO — GitHub Free-Only Engineering Policy

**Status:** proposed with PR #376; do not assume it is live until reviewed and merged.

## Spend guardrails

- The code owner currently is the **personal `kmjtechno` account** and `kmj-main-platform` is **private**. Do not publish commercial source just to gain unrestricted public-project Actions minutes.
- For GitHub Free, standard GitHub-hosted runners in private repositories include 2,000 minutes/month. Usage above the included allowance must remain **$0 additional spend**.
- In the account's Billing & licensing > Budgets and alerts, maintain a **$0 Actions metered budget with Stop usage enabled**, and keep the included-usage 90%/100% notifications enabled. Keep other paid products at $0 unless separately approved.
- A previously incurred bill or billing restriction needs GitHub Billing Support resolution; changing workflow YAML or adding a new spending budget cannot cancel old charges. Never auto-pay, enable a paid overage, run larger paid runners, or silently increase any cap.
- Monitor **account-level** included minutes and artifacts; the screenshot's **$0 spent** is not the same as “0 minutes used”.
- Keep `GITHUB_TOKEN` permissions minimal and pin third-party Actions where practical. Do not pass deployment secrets to untrusted pull requests. No disabling of required checks or protected branch approvals.

## Maximum useful execution from free runners

- **Deploy only after a successful approved promotion:** `Staging VPS Deploy` keeps `workflow_run` from `Staging Promotion Gate` and manual `workflow_dispatch`. A 6-hour scheduled drift watchdog is a backup, not a second deployment path.
- Scheduling: 15-minute recurring staging checks would produce up to **96 invocations/day** (~2,880/month). Six-hour schedule is **4/day** (~120/month), cutting the potential scheduled invocation count **95.8%**. Actual billed minutes depend on individual run durations and cancellation.
- **Cancel stale per-PR checks**, not current release gates: preserve workflow job names and trigger paths. `server-infra-ci.yml` uses concurrency cancellation to avoid spending minutes on superseded commits.
- Keep PR verification meaningful: Laravel, PHPStan, Pint, TS, Node, Rust, database and CodeBridge tests must execute and pass. “Failed with zero steps” indicates startup/configuration/billing problem, **not** a test assertion failure.
- Existing 5-minute autonomous self-hosted workflows are a separate engineering system; this PR does not modify their scheduling or their permissions. Those workers still need device-health, device-scoped authorization and isolation checks.
- Keep Node/npm cache scoped to lockfiles, prefer Ubuntu standard runners, short timeouts, minimal artifact retention (3 days for staging screenshots) and local development preflight before PR pushes.
- Prefer KMJ CodeBridge's approved free local QA device for temporary PR-head tests; do not deploy untrusted test branches into production or use a production DB for CI.
- Codespaces may offer included personal-account resources; use only if genuinely needed and under the existing $0 cost cap.

## Restoring protected GitHub Actions

1. Check [personal account billing overview](https://github.com/settings/billing) and [payment history](https://github.com/settings/billing/payment_history) for any past-due usage invoice or disabled paid features.
2. Contact [GitHub Billing Support](https://support.github.com/contact/account?type=billing) to request a statement review/correction or waiver, and clarify whether the account's **included Free Actions minutes** can be used while paid features are disabled.
3. Inspect the earliest failed workflow's GitHub UI annotations and account [Actions usage](https://github.com/settings/billing/usage). Do not infer the root cause merely from all workflows failing.
4. Once GitHub explicitly confirms a resolution, rerun exact-head protected CI; only then consider merging PR #376 and the independent admin/license release PR #375. No bypass of protection or paid actions.

Sources: https://docs.github.com/en/billing/reference/product-usage-included,
https://docs.github.com/en/billing/how-tos/set-up-budgets,
https://docs.github.com/en/actions/concepts/billing-and-usage
