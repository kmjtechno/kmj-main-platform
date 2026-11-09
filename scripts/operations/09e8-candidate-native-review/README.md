# Exact 09e8 candidate-only cutover — source review lane

This directory is a **non-executable native adapter review**, adapted from the
earlier CD958 guarded transaction without running any production operation.

## Fixed release geometry

- Live: `/home/kmjprod/releases/platform-bce4100d005e`.
  Existing `apps/platform/storage` is a symlink to `/home/kmjprod/shared/storage`.
  Its pointer and shared-directory inode MUST never change during candidate
  storage preparation.
- Target: `/home/kmjprod/releases/platform-09e8a224cd37/apps/platform/storage`.
  It begins as a **physical directory**, and the v6 scanner may target only
  this candidate path, never the live runtime app path.
- Root materializer:
  `/usr/local/libexec/kmj-codebridge/main-platform-candidate-materialize-v2.sh`;
  SHA256 `fd29c4ebcf224c45786f8cedd0e0d42bbfd414d706678fe820e0ead4eea3984f`.
- Root v6 scanner:
  `/usr/local/libexec/kmj-codebridge/main-platform-storage-switch-v6.py`;
  SHA256 `f4d01f6e3b40c9ad774c8ada5129b241cee93dac782ce75bb0e229b26bbc95ba`.
- Root snapshot helper SHA256
  `72fe5702c59599bd1b28b88dad808dda5d6be97b61f0db06dc3a7295258a51b6`.

## Security conditions

The source contains the prior reviewed nftables output guard, live PHP-FPM
pool idle/drain, fixed queue/scheduler timer control, durable journal and
recovery routines, but is **NOT wired to an owner-run apply entrypoint**.
`orchestrator.py` always returns
`BLOCKED_NATIVE_ADAPTER_NOT_IMPLEMENTED`; there is no root installer,
systemd service unit or executable apply contract in this lane.

The old CD958 command SHA fingerprints are intentionally invalid and are
NEVER reusable for the bce410 live runtime. A future independent root audit
must attest both exact current command signatures (without leaking argv or
secrets) before the writer admission gate could be made available.

Current CI covers copied historical adapter regression tests and exact-target
candidate-only negative tests. It does **not** establish process drain,
recovery under real ext4 immutable flags, trusted active firewall exclusion,
snapshot durable receipt, owner-authenticated QA, staging approval, rollback
or production release readiness.

DO NOT run an old CD958 operator script, invoke the native adapter manually,
replace the live storage link, or manually edit protected approvals. Further
reviewed work is required for root-private journal directory provisioning,
complete kernel fault-injection tests, and an owner-authorized bounded
executor with recovery before any host mutation.
