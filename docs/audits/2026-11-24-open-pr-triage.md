# Open PR triage — 2026-11-24

Snapshot of the 41 non-draft open PRs (of 157 open; 116 are drafts and are not triaged here).
CI = check runs on each PR's exact head at read time. `mergeable_state` was not computed by
GitHub for most PRs, so conflicts with current `main` (359b20f) are NOT known.
All PRs are owner-authored; Claude merges only PRs it opened. This is a recommendation list,
not a merge decision, and green CI is not release evidence (see RELEASE_GATE.md).

## A. Green on exact head (review/merge candidates)
| PR | Head | Topic |
|----|------|-------|
| #1123 | 00057ef | default-off inbound email pilot |
| #1120 | 0597026 | KSLP checkout and refund correlation |
| #1118 | 50ea1aa | KSLP reviewed commercial terms, sandbox checkout binding |
| #1117 | cac0f67 | KSLP signed reversal correlation |
| #1093 | 6e36bda | CodeBridge tenant usage read model (source only) |
| #1092 | fc7825f | CodeBridge device job receipt gate (source only) |
| #1087 | 5b3d81d | CodeBridge monthly usage ledger (source only) |
| #1068 | 136ebad | Razorpay sandbox trust/race gates |
| #1064 | c7501da | unifies #928/#929/#1056 Razorpay sandbox work |
| #993 | 35aadea | fence PostgreSQL writers before purge |
| #979 | 5d41cf2 | OmniDesk key isolation on unified Licensing Hub |
| #967 | fea0883 | Licensing Hub key isolation refresh |
| #934 | 3a72367 | nonroot PostgreSQL18 + AGE recovery image |
| #929 | 0e3a3d1 | Razorpay durable provider-order intent |
| #928 | e717d8e | Razorpay early-webhook recovery |
| #888 | 7a53a69 | P520 recovery evidence (80 files, review carefully) |
| #618 | b6f7788 | staging storage continuity + disposable DB restore |
| #601 | 40e3a92 | staged release candidate backup + isolated restore |
| #299 | c39be44 | CodeBridge pairing gateway |
| #273 | b7590be | PHP 8.3 production compatibility (old; recheck need) |

## B. Overlaps — pick one stack
- Razorpay sandbox: #928, #929, #1064, #1068. #1064 states it unifies #928/#929/#1056; prefer #1064 (+#1068 if it is the later fix) and close the rest after diff review.
- Licensing Hub key isolation: #967 and #979 touch the same area; confirm which supersedes.
- Pricing: #1082, #1125 (see also drafts #1061, #1091).

## C. Failing CI on head (do not merge; likely stale)
#1125 (2 failed), #446, #443, #429, #421, #401, #385, #370, #368, #367, #364, #362, #359, #321.
Most date from Sept–Oct on old bases. Rebase on current `main` or close; #429 is a security
fix (block unauthenticated CodeBridge super-admin) and should be checked against current
code first because it may already be fixed.

## D. Cancelled / no checks
- Cancelled runs: #325, #282, #274, #270, #265 (old UX/customer-portal PRs; likely superseded by the owner console).
- No check runs yet: #1082, #978.

## Suggested order
1. Owner enables `main` protection with required check `verify`.
2. Close superseded Razorpay/KSLP duplicates after diff review.
3. Merge green, non-overlapping PRs one at a time, re-reading CI after each merge.
4. Rebase or close section C.
5. Admin QA (authenticated) before any release claim.
