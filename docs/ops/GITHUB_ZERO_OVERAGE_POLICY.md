# KMJ TECHNO — zero additional spend policy

## Financial contract

**Maximum incremental metered spend: USD 0 / INR 0.** This is **in addition to** owner-approved existing subscriptions (for example, GitHub Pro and existing VPS/VM charges); it does **not** mean that those subscriptions are free.

- No automatic upgrade, new subscription, credit-card authorization, metered AI API/model use, larger paid Actions runner, cloud instance, Codespaces, or package storage purchase.
- GitHub **Pro includes 3,000 Actions minutes and 1 GB Actions/Packages storage for private repositories** per billing cycle, subject to actual active account plan. Never infer current usage from these maximum allowances.
- Existing standard GitHub-hosted runners may consume the included allocation only after the account owner has verified **hard-stop budgets**. If the quota/budget stops hosted CI, run the same tests on an approved already-paid VPS/VM in isolated worktrees; keep required hosted checks **red/pending**, unless branch protection is explicitly and safely changed through owner release governance. Never fabricate green CI.
- GitHub Actions on private repositories are billed to the **repository owner**, which in this case is the personal `kmjtechno` account. Repo YAML and locally enforced checks **cannot** prevent account-level charges; only billing controls can.
- Existing free AI quota is allowed only with legitimate credentials and applicable provider data policies. `paid_ai_fallback: prohibited` remains in `mission/main-platform.yaml`; paid API keys/routes are disabled by default. When no compliant free model is available, queue work with `NO_FREE_ROUTE_AVAILABLE` or activate a verified low-resource local fallback only on demand.
- Do not use public repositories merely to obtain unmetered minutes if they expose private KMJ code.

## Owner action required to make the hard stop effective

1. Sign into the **same GitHub personal account that owns the private repository**, and verify the Pro upgrade has actually completed at https://github.com/settings/billing (a checkout screen alone does **not** prove payment).
2. Open **Budgets and alerts**. Create or inspect a **Product-level GitHub Actions budget** for the entire personal account, choose **USD 0** incremental budget if supported, and enable **Stop usage when budget limit is reached**. Do not use alert-only mode as a hard stop. Check for overlapping SKU/repository budgets and how they affect included minutes. If GitHub blocks included usage under a zero budget, stay with local CI rather than raising the spend cap.
3. Review separate **Codespaces, Packages and Copilot/AI credits** budgets/usage. Set zero incremental limits/hard stops where supported, and do not enable paid SKUs. Turn on the included-usage alerts at 90% and 100%.
4. Verify dashboard shows metered spending **USD 0**. The GitHub token currently available to KMJ VPS has `repo`/`workflow` scopes but lacks the billing `user` scope, so local automation **cannot verify or modify this budget**. Never mark the hard stop as confirmed without an authenticated billing readback.

GitHub documentation: https://docs.github.com/en/billing/how-tos/set-up-budgets and https://docs.github.com/en/billing/reference/product-usage-included

## CI scheduling policy

The CodeBridge License Contract, Device Pairing and OAuth hosted workflows retain their existing paths, permissions and required checks, and now **cancel obsolete runs on the same PR/ref**. Newest commit runs remain eligible. Do not add GitHub larger runners. Preserve normal quality gates, independent approvals and branch protection.

Use fast local tests on changed files before full suites. Stop or defer hosted Actions when included usage is near exhaustion; never turn a failed/pending required check green artificially. Do not let automated re-run loops burn remaining free minutes. Any budget override requires a separate explicit, authenticated owner decision.

This document is a **repository policy and operator checklist, not evidence that the GitHub billing hard stop is already set**.
