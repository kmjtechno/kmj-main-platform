# Staging Monitor Guide

This guide helps operators interpret the staging monitor and enqueue routine low-risk work. It is a companion to deployment and CI docs, not a replacement.

## Monitor endpoints

- Monitor page: https://staging.kmjtechno.com/info
- JSON status: /info/status
- Refresh: every 5 seconds; retains at most 60 browser samples.

## Metrics table

| Metric | Meaning | Operator note |
| --- | --- | --- |
| VPS load | 1-minute Linux load average divided by visible CPU count, expressed as a percentage. | Not measured CPU utilization; cannot alone prove idle or saturated CPU. |
| Memory | MemTotal minus MemAvailable. | Reclaimable cache can explain provider panel difference; available memory is useful capacity, not waste. |
| Queue | Application queue rows and artisan queue:work processes. | Distinct from the GitHub autonomous worker. |
| GitHub runners | Two self-hosted runners execute independent CI work. | Composer/npm dependency installation overlaps; PHP checks overlap frontend checks after the build. |
| Staging deploy write | Shared flock serializes staging deployment writes. | Do not expect concurrent deploy writes to succeed. |
| Autonomous worker | Wakes on main pushes, safe issue events, and a five-minute schedule. | Scheduling is not a five-minute completion guarantee; at most three open, non-conflicting task PRs; changes go through validation and CI. |
| AI monitor evidence | Recent completed zero-cost response and its UTC timestamp. | Not a promise of continuous generation; evidence accepted for 30 minutes; idle cycles make no artificial calls; no inference model runs on the VPS. |

## Task steps

1. Open a narrowly scoped issue with exact acceptance criteria.
2. Apply the `autonomous-safe` label.
3. Check worker status labels:
   - `autonomous-running` means the worker claimed the work; inspect the linked PR and its checks.
   - `autonomous-blocked` means review the issue explanation before acting.
4. Inspect the linked PR and its checks rather than repeatedly reopening the issue.
5. Use the official free cloud client: OpenCode CLI with the fixed `opencode/big-pickle` model, isolated configuration, and tools denied.
6. Each request requires a fresh published zero-price check and a zero-cost result; stop if verification or availability fails.
7. Paid fallback is prohibited; unknown cost is not free.

## Troubleshooting checklist

- Monitor not updating: check /info/status; the page refreshes every 5 seconds and keeps at most 60 samples.
- VPS load high: inspect runners, queue, and deploys before concluding saturation; load alone is not proof.
- Memory differs from provider panel: compare MemAvailable and account for reclaimable cache.
- Queue rows growing while queue:work is idle or erroring: investigate; otherwise active workers are expected.
- Deployment not reflected: verify exact deployed commit evidence, database health, and authenticated smoke results.
- `autonomous-blocked`: read the issue explanation and linked PR checks; reopen only with new evidence.
- AI evidence stale: evidence is accepted for 30 minutes; idle cycles make no artificial calls.

## Release confirmation

A successful release is confirmed by exact deployed commit evidence, database health, and authenticated smoke results, not merely by a workflow that started.
