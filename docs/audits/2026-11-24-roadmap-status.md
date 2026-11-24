# Main Platform roadmap status — 2026-11-24

Evidence-based comparison of `KMJ_TECHNO_MAIN_PLATFORM_MASTER_ROADMAP_BLUEPRINT_V1_0.md`
(snapshot 10 Sep 2026) against `main` at `786e5b00589b65e642795cc315767a4c7fb3f2c6`.
Status words follow roadmap section 26. Nothing here is a release-readiness claim:
RELEASE_GATE "ADMIN QA" has no live evidence for this head.

## Live facts verified today
- Production runs `platform-c9f908e5c09b`; 0 pending migrations; live smoke 200/200; public desktop/mobile QA PASS (that SHA).
- `main` head 786e5b0 (#1126 owner-nav fix). CI `verify` and `verify-server-infra` success; staging candidate job was still running when read.
- Open PRs: 157 (116 draft, 41 non-draft), all by the owner account. Oldest 2026-09-30.
- `main` branch protection: no required reviews, no required status checks (roadmap Priority 0 still open; owner-only setting).

## Priority backlog (roadmap section 24) vs repository
| # | Item | Evidence on main | Status |
|---|------|------------------|--------|
| 0 | Branch protection | API shows none | BLOCKED (owner) |
| 1 | Authority Slice A (orgs, catalog, entitlements) | `packages/domain-{organizations,catalog,entitlements,identity}` exist; only 12 Eloquent models in app | IN_REVIEW, needs per-item test evidence |
| 2 | Licensing / signed lease / Rust verifier | `services/license-core`, `contracts/kslp-v1`, KSLP migrations, revocation + audit tables | ACTIVE; interop PRs (#895, #1039, #967, #979) unmerged |
| 3 | Passkey + org integration | passkeys migration exists; org/tenant context not verified | PLANNED/ACTIVE, unverified |
| 4 | Transactional outbox | `domain_outbox_*` migrations + models | ACTIVE (consumer idempotency tests not re-run) |
| 5 | Audit foundation | `operator_action_audits`, `license_audit_events` | ACTIVE (append-only enforcement not re-verified) |
| 6 | Release trust | `packages/domain-releases`, Release Center page | ACTIVE |
| 7 | Commerce origin | provider order + webhook tables; Razorpay sandbox PRs (#928, #929, #1064, #1068) unmerged | IN_REVIEW; no LIVE payment proven |
| 8 | Kristi safe foundation | ADR-005 only found | PLANNED |
| 9 | Public IA | public marketing pages exist | ACTIVE |
| 10 | Old-site inventory (P0-02) | `docs/inventory/public-surface.yaml` | IN_REVIEW |

## Real bottleneck
Roughly 157 open PRs, mostly drafts, many stacked or superseded (several OmniDesk M9 and KSLP PRs
overlap the "unified Licensing Hub" PRs; Razorpay has at least four overlapping PRs). Writing
more code does not advance the roadmap until this backlog is triaged. Triage needs owner
decisions (which stack wins, which drafts to close); Claude does not merge PRs it did not open.

## Open product bugs found today (admin UI audit)
- Fixed: Communication link (#1126). Remaining: several sidebar labels share one destination
  (OmniDesk, CineCore, Content -> /operator/products; Task Automation, System Settings, Backup Status -> /operator/ops).
- Nav defined in three files; dashboard and owner pages use different shells (UI mismatch).
- Disabled ops buttons show no reason text.
- SMS has no page.

## Next dependency-ready slices
1. Owner: enable `main` protection with required check `verify` (no code needed).
2. Claude: PR-triage report of the 157 PRs grouped by stack, with CI state of each exact head, recommended keep/close.
3. Claude: one shared owner-nav definition; honest "coming soon"/real destination for duplicate labels; reason text on disabled ops buttons.
4. Owner: authenticated ADMIN QA session (needed for any release claim).
