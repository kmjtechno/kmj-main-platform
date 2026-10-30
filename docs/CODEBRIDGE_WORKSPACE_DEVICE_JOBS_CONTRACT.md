# CodeBridge Workspace device tool requests (contract v1)

Status: Main Platform side implemented behind `CODEBRIDGE_WORKSPACE_JOBS_ENABLED=false` (default off).
**No device agent consumes this queue yet.** Until the KMJ CodeBridge agent implements the client below and an operator turns the flag on, requests cannot be queued from the UI and nothing is claimed.

## Trust model
- Main Platform is only a request queue and the record of what a device reported. It never executes anything.
- A signed-in user may queue only catalogued tools (`WorkspaceToolCatalog`): `git_status` (read), `inspect_project` (read), `quality_gate` (execute, argument `gate` = configured gate id `^[a-z][a-z0-9_-]{0,39}$`). No free-form command, path or shell text exists in the schema.
- The pairing's granted permissions are checked when queueing **and again when the device claims**. The device must additionally enforce its own administrator policy (gate must be configured locally) before running.
- Requests are private to tenant + user + device + project; at most 5 unfinished per project; unclaimed requests expire after 15 minutes.

## Device API (bearer = the device credential already used for lease renewal)
Base path `/api/codebridge/v1`. Responses are `Cache-Control: no-store, private`. 503 while disabled.

`POST /jobs/claim` -> `{"job": null}` or
`{"job": {"id", "tool", "arguments" (always a JSON object, `{}` when empty), "project_id", "lease_expires_at", "claim_token"}}`.
One request in flight per device. `claim_token` is returned once and must be sent as header `X-KMJ-Claim` on every report.

`POST /jobs/{id}/events` body (<=16 KiB):
- `{"kind":"started"}` claimed -> running
- `{"kind":"progress","progress":0-100,"detail":"<=500 chars"}` (monotonic; extends the 120 s lease)
- `{"kind":"succeeded"|"failed","summary":"<=2000","evidence":{...}}` — `succeeded` requires a prior `started`; `failed` is also accepted directly from `claimed` so a device can refuse a request (unknown gate, project not enabled locally, dirty checkout) without running anything.

Evidence keys allowed: `commit_sha` (40 hex), `gate`, `ci_url` (https://github.com/<o>/<r>/actions/runs/<n> only), `exit_code`, `duration_ms`, `result` (`pass|fail`). Anything else is rejected (422).
`409 {"error":"job_not_active"}` means cancelled, expired or finished: **stop immediately**. A cancel may arrive while the device is already running; the user is told that a local run may still be finishing.

## States
queued -> claimed -> running -> succeeded | failed ; cancelled (user) ; expired (unclaimed) ; failed `lease_expired` (device went silent: outcome unknown, never shown as success).

## Not proven
Real device round-trip, the agent client, production enablement, and any 24x7 worker. Hosted CI exercises the Main Platform side only.
