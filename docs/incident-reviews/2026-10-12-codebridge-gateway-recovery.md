# Incident review: CodeBridge gateway stale MCP tool catalog (12 October 2026)

**Status:** production catalog discrepancy resolved; client-level Local LLM validation continued separately.  
**Severity:** P0 service-capability mismatch, not confirmed data loss.  
**Affected endpoints:** `https://kmjtechno.com/mcp` and the colocated agent data plane.  
**Evidence:** [Main Platform issue #383](https://github.com/kmjtechno/kmj-main-platform/issues/383), [CodeBridge issue #295](https://github.com/kmjtechno/kmj-codebridge/issues/295), [CodeBridge PR #296](https://github.com/kmjtechno/kmj-codebridge/pull/296).

## Verified source of the incident

Production Nginx routed both `location = /mcp` and `location ^~ /agent/` to a single loopback process at `127.0.0.1:18787`. It was `kmj-codebridge-gateway-stage.service`, running as `kmjcode` with Node.js 24.21.0 in `/srv/kmj-codebridge-projects/kmj-codebridge`.

The running Git checkout was clean at exact commit `6b6d7051f3a4a15f6fadc6dcc53e51e54bbd65d1`. It advertised 88 MCP tools and did not include `local_model_generate` in `src/tools.js`, even though its package version was 0.3.2. By contrast, the Render deployment at `055fd88ebfd56125abbe2bcec8f99819ed54ae80` advertised 101 tools, including `local_model_status`, `local_model_generate` and `autopilot_local_draft`. GitHub commit comparison established that the Render commit was a descendant 16 commits ahead of the VPS runtime.

A separate Laravel CLI bootstrap classified a configured `127.0.0.1:8787` gateway with no listener. This was **not** the actual active public MCP upstream; Nginx directly proxied the public route to port 18787. Do not attempt to repair the incident by blindly changing Laravel's `CODEBRIDGE_GATEWAY_URL`.

## Resolution, as observed by operator

1. Staged exact source commit `055fd88ebfd56125abbe2bcec8f99819ed54ae80` in `/opt/kmj-codebridge-candidates/<SHA>`, keeping the original production checkout clean.
2. Under the `kmjcode` user and Node 24, `npm ci`, `npm run check`, `npm test` and `npm run scan:secrets` all passed.
3. The operator ran the one-time, SHA-256-checked recovery utility as root on `KMJ-elite`. Its preflight passed, it installed a systemd drop-in to select the pinned candidate runtime with the existing private gateway configuration, and restarted only the gateway service.
4. The utility reported `CUTOVER=PASS`, new PID `139556` and direct, local Nginx and public MCP tool counts **101 / 101 / 101**. Backup directory: `/var/backups/kmj-codebridge/20261012T184729Z`. No Nginx rewrite, DNS migration, or deliberate OAuth/agent credential change was made.
5. The independent CodeBridge PR #296 acceptance workflow was rerun; Render and public-domain catalog jobs both passed (full PR CI verdict 10/10 green on exact head `3ca9357941890f20ca2d224944249b564cd2b9a1`).
6. After cutover, four enrolled devices appeared online with fresh gateway heartbeats; permitted gateway-to-agent jobs were executed: Main Platform fast gate 4/4 PASS, CloudOS fast suite 31 PASS, P720 real Ollama inference for `qwen2.5-coder:7b` and `qwen3:4b` PASS, and P720 AI unit tests 6/6 PASS.

These observations substantiate **MCP catalog and existing agent command path recovery**. They do not by themselves substantiate every customer OAuth path, signed install flow or autonomous AI workflow.

## Archived one-time operator utility

For review provenance, the exact utility used by the production operator is stored as **plain-text evidence**, not as an executable deployment automation:

`docs/incident-reviews/evidence/2026-10-12-codebridge-gateway-cutover.py.txt`

Original observed SHA-256: `461d8e4252467b3e63c3bade7b85e89ed40fc5d898edd735bb73c2ad95b7cf32`.

**NEVER EXECUTE OR REPLAY THIS ARCHIVED SCRIPT.** It is pinned to an already-completed old-to-new cutover, assumes an old 88-tool baseline, and uses root-level systemd mutations. It is deliberately named `.txt` to make the archive inert. The untracked original is still present in the active Main Platform CodeBridge checkout under `ops/codebridge-gateway-cutover-20261012.py` pending separate authorized cleanup. This review PR does **not** remove, run, redeploy or otherwise mutate that live file or service.

## Known limitations and follow-up safety work

- The one-time utility was **not reviewed as a PR before it ran**. This PR records and enables retrospective review; it cannot retroactively grant prior approval.
- The utility attempted rollback on error, but a successful forward deployment does **not** exercise or prove that rollback path. Explicit recovery rehearsal and bounded service downtime budgets remain future release gates.
- Gateway pending jobs are in memory; avoid service restarts with active requests. Future deployments need an explicit drain, in-flight job check and rollback decision, rather than trusting a zero-queue snapshot alone.
- Archive includes fixed hostnames, on-host paths and exact source SHAs but no private token values. Do not publish private gateway configuration JSON, environment values or signed credentials.
- The catalog tool count does not prove full client tool invocation. A subsequent Claude report states real authenticated `local_model_status` and `local_model_generate` succeeded for **`qwen3:8b`** with `/no_think` at the end of its prompt, `maxTokens:512`, `paidInference:false` and `cloudFallback:false`. That is a reported separate model/device observation, **not** direct confirmation that the P720's `qwen2.5-coder:7b` / `qwen3:4b` can be invoked through the same Claude connection.
- `autopilot_local_draft` still requires a legitimate leased task and was not tested; do not invent task IDs or lease tokens.
- ChatGPT's existing connected CodeBridge surface still exposed older tool definitions during the incident review; obtain a supported connector refresh and verify a real authenticated call rather than bypassing MCP tool registration.
- For **future** production releases, build a separately reviewed, parameterized deployment controller with explicit operator consent, immutable verified sources, isolation, dry-run, health/OAuth/agent end-to-end checks, job draining and **tested** rollback. Do not copy this one-time utility into a reusable updater.

## Review / release policy

This is a documentation-and-evidence-only **draft PR**: it makes no runtime behavior changes and must not trigger a new CodeBridge cutover. Exact-head CI and independent reviewer acceptance are required before merge. As stated in `RELEASE_GATE.md`, passing unrelated `main` checks does not establish this PR's release readiness. Do not treat an Actions budget or remote supervisor limitation as a reason to waive checks.
