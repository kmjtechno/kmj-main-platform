# V3 backup blocked: certbot matrix drift (26 Nov 2026)

Status: `BLOCKED` (fail-closed by design). Evidence: receipts on KMJ-elite
`work/qa/kmj-receipts/v3-certbot-drift.txt`, `v3-matrix-text.txt`, journal of
`kmj-v3-dual-local-health.service` at 15:45 IST.

## What happened
- The V3 daily run exited 3 with `BLOCKER=CERTBOT_MIXED_SOURCE_MATRIX_DRIFT`,
  `RESULT=BLOCKED_FAIL_CLOSED`. No V3 snapshot was made on 26 Nov.
- The guard (`validate_certbot_live_matrix`, repo
  `scripts/KMJ_OFFSITE_V3_DUAL_LOCAL_HEALTH_ONEPASS_20261117.py`, installed as the
  `...-20261118.py` variant) accepts exactly: 3 lineages, 8 standard links,
  4 regular PEMs.
- Live `/etc/letsencrypt/live` now has 4 lineages. The pinned shape was
  `cloudos` (4 links), `staging` (4 links), `kmjtechno.com` (4 regular PEMs).
  New: `mail.kmjtechno.com` (4 links, directory mode 0755 instead of 0700, created
  26 Nov 11:26 UTC with its renewal conf). That adds 4 links and a 4th lineage.

## Why it is not bypassed
The guard protects the backup from reading unreviewed certificate material.
Widening it is a reviewed, pinned change, not a hotfix.

## Options (owner decides)
1. **New pinned V3 version** that expects 4 lineages / 12 links / 4 regular PEMs and
   requires `mail.kmjtechno.com` to be root-owned with standard links. Needs: updated
   guard, matching hash pins in the publisher/installer set (both libexec directories),
   tests with a 4-lineage fixture, owner-run SHA-pinned install. Recommended.
2. Move the mail certificate outside `/etc/letsencrypt/live` (mail lane change).
   Not recommended: breaks certbot renewal layout.
3. Leave V3 blocked and rely on the 08:05 job. Not acceptable: V3 is the
   encrypted dual-local copy.

## Interim protection (verified 26 Nov)
Daily snapshot `20261126T023521Z`: restore drill PASS, storage check PASS (9/9).
Off-host restore and retention remain unproven/unapproved.

Nothing here claims production readiness.
