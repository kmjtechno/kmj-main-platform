# Production readiness matrix — 2026-11-27

Against `main` 7b95b21 (after #1252). Sources: `RELEASE_GATE.md`, roadmap sections 17.3, Phase 3 and Phase 7 exit gates. This is an evidence map, not a release claim. Status words follow roadmap section 26; "TESTS IN CI" means source tests exist and run in the PostgreSQL 18 feature job, not that the exact release candidate was accepted live. Live release is `platform-f4e7f1331d5f`; `main` has newer source (refund record, scripts, tests, docs) that is not deployed.

## A. RELEASE_GATE (fail closed)
| Gate | Status | Evidence / gap |
|---|---|---|
| BUILD | NO EVIDENCE for a new candidate | Needs `quality-gate full` on the exact candidate head |
| DIFF | CI covers per PR | `git diff --check` runs in CI |
| ASSETS | PASS (live, earlier SHA) | Public QA job `f6ec591d`: 0 broken images; repeat on new candidate |
| DESKTOP / MOBILE QA | PASS on live `f4e7f13` (2026-11-26) | `/`, `/products`, `/login` at desktop, tablet, mobile: 200, 0 overflow, 0 exceptions |
| ADMIN QA | NO EVIDENCE | Read-only GET sweep of 11 owner pages returned 200 (2026-11-27). Create/edit/lifecycle/ordering controls NOT exercised; needs owner consent for a test product |
| LIVE SMOKE | PASS on current live release | Must be repeated after any deploy |

## B. Recovery contract (roadmap 17.3)
| Item | Status | Evidence / gap |
|---|---|---|
| Encrypted backups | TESTS + RECEIPTS | V3 guard PASS (manual 11-26, systemd one-shot 11-27 08:01); vault sidecar 54/54 hash match |
| Local restore drill | PASS (same host) | snapshot 20261126T133036Z, storage check 9/9 |
| Separate account/host copy | NOT DONE | `OFFSITE_UPLOAD=NOT_ATTEMPTED_LOCAL_ONLY` |
| Off-host restore | NOT DONE | Owner must supply target; see `offhost-restore-proof-plan-20261127.md` |
| Decrypt with recipient key | NOT DONE | Key custody is owner-only |
| PITR | NOT DONE | Daily `pg_dump` only |
| 15:45 IST calendar timer | PENDING | First scheduled run 2026-11-27 15:45 IST |
| RPO/RTO claims | FORBIDDEN | No measured restore time |

## C. Phase 3 exit gate (commerce and licensing)
| Gate | Status | Evidence / gap |
|---|---|---|
| Purchase-to-revocation flow | TESTS IN CI (sandbox) | `FirstVerticalSliceAcceptanceTest::test_authenticated_owner_completes_first_vertical_slice_end_to_end`. No real order exists in live data (Command Center shows 0 orders) |
| Signing-key isolation | TESTS IN CI | `KslpKeyRotationTest::test_key_domains_rotation_and_revocation_are_separate` |
| Key rotation | TESTS IN CI | `KslpKeyRotationTest` (5 tests incl. revoked kid cannot be republished, not-before/not-after) |
| Offline grace cases | TESTS IN CI | `KslpOfflineLeaseGuardTest` (stale sequence, clock rollback, revocation during grace, excess window, forged signature) |
| Device activation limits | TESTS IN CI | `CodeBridgeDeviceEnrollmentTest::test_device_limit_is_enforced_before_credential_creation` (CodeBridge devices; other products need their own proof) |
| Revocation latency | PARTIAL | Online/server validation: a revoke is a DB row read on the very next validation (`SandboxLicenseValidationEngine`, `LicenseRevoker`), tested by `SandboxLicenseLifecycleTest::test_signed_sandbox_license_can_be_validated_and_revoked` and the first-vertical-slice acceptance test, so no cache delay. Offline clients: bounded by the signed offline window and grace (`KslpOfflineLeaseGuardTest` rejects excess windows and known revocations during grace); the real time for a disconnected client to learn of a revoke is NOT measured, and no client-side revocation sync latency test exists |
| Rust wrapper conformance | CI job exists | "Native Rust license verifier" and interoperability jobs pass on main |
| Live payments | NOT DONE | Razorpay sandbox only; live charging locked; manual UPI/bank details not decided |
| Refund | PARTIAL | Owner-only record of a refund made in the provider dashboard (#1247-#1249); no provider refund call, no license revocation link |

## D. Phase 7 exit gates (cutover)
| Gate | Status |
|---|---|
| Content parity / redirect map | NO EVIDENCE (inventory file exists: `docs/inventory/public-surface.yaml`) |
| Data parity | NO EVIDENCE |
| Security: key rotations tested | TESTS IN CI (see C) |
| Backup restore tested | PARTIAL (same host only) |
| Degraded mode, queue replay, rollback exercised | NO EVIDENCE found in this review |
| Performance budgets | NO EVIDENCE |
| Product compatibility (Nexus, sandbox clients) | NO EVIDENCE |
| Owner production-change form | NOT COMPLETED |
| Privacy data inventory, DPDP legal review | NO EVIDENCE (legal pages exist; inventory doc not found) |

## E. Open items by owner
1. Restore target host and recipient-key custody.
2. Consent for a test product to complete ADMIN QA.
3. Live payment method decision and Razorpay sandbox test order click.
4. PR triage decisions (`2026-11-27-open-pr-triage.md`).
5. Deploy approval and production-change form.

## F. Dependency-ready for Claude
1. Document the maximum offline window per product (the real upper bound of revocation latency for disconnected clients) and add a client-sync revocation test.
2. Refund-to-revocation explicit owner action with tests.
3. Redirect map and privacy data inventory drafts.
4. Check the 15:45 IST V3 run and record the receipt.
