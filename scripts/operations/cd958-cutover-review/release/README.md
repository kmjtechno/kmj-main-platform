# CD958 release operator record (KMJ-elite, 2026-11-07)

These are the exact operator scripts that took candidate `cd9580701d3cea19d7d4e4c96ebe70c0553fbf37`
live. They were staged in the ELITE project checkout and run as root by the owner. Each paste
command verified the SHA-256 below before executing a root-owned copy. Results were written to
`work/qa/` on ELITE.

| File | SHA-256 | Purpose |
| --- | --- | --- |
| `KMJ_CD958_CUTOVER_OPERATOR_1A7F4A8_20261107.sh` | `a13512c6c0bff8298ee7662b71946d970e868046d741f42a250c81a04d61f1de` | Builds the cutover bundle from commit `1a7f4a88` blobs (git as the project owner), installs it only if it hashes to `e64ec2f5…`, runs `inventory`/`preflight`/`apply`/`materialize` in their own systemd units. |
| `KMJ_CD958_MIGRATION_REHEARSAL_20261107.sh` | `109c72763f316f90768389b3e0035e725e07b3aea798330b19645202e7242878` | Disposable PostgreSQL restore of the pre-deploy backup; exact 4 migrations up, 574e compatibility, down, up. No production DB write. |
| `KMJ_CD958_CONTROLLER_6D6D_TO_B192_20261107.patch` | `fddf68837058c9d49db1c8489d196f6f4b351016352421a01a43739133c8f98b` | Turns the installed controller `6d6d2788` (`ae42b9f1…`) into merged kmj-codebridge `b192a2e5` (`daa789f2…`), which verifies the preserved storage dir through the protected attestor. |
| `KMJ_CD958_RELEASE_FINISH_20261107.sh` | `46955f9195cc3214db97e3d2ce39fdcc6a9e273075eaa17caca782f16dd18908` | `controller`, `migrate` (exact 4 additive migrations), `approve`, `activate` through the existing guarded release unit, `rollback` (emergency pointer back to 574e) and `status`. |

## Executed sequence and observed results

| UTC | Step | Result |
| --- | --- | --- |
| 11:19 | operator `readonly` | bundle `e64ec2f5` installed; inventory rc 0; preflight 11/11 true; no mutation |
| 11:20–11:21 | operator `apply` | `storage_complete_materializer_pending`; materializer PASS (env byte-identical, nginx env denied, pointer 574e unchanged) |
| ~11:27 | migration rehearsal | `ISOLATED_MIGRATION_DRILL=PASS` |
| 11:33 | release `finish` (run 1) | controller upgraded to `daa789f2`; migrate precheck BLOCKED before any write (work dir under `/root` unreadable by kmjprod; fixed in `46955f91`) |
| 11:37 | release `finish` (run 2) | 4 migrations applied; approval written (previous kept); `MAIN_PLATFORM_ACTIVATION_PASS cd958…`; pointer `platform-cd9580701d3c`; git HEAD cd958; `/login` and asset 200; queue restarted on cd958 |

## Limits

- `rollbackVerified` in the protected approval rests on the migration down/up rehearsal, the old release
  reading the expanded schema, and the controller's automatic pointer rollback. The controller's
  rollback path was not separately rehearsed for this release.
- Authenticated owner UI/Workspace QA is the owner's step; it is not recorded here.
- Preserved `storage.pre-shared-*` directories and the previous controller copy are retained. Do not delete them.
