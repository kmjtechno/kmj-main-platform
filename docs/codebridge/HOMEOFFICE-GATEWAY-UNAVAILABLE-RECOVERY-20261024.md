# KMJ TECHNO | Home Office CodeBridge pairing recovery (2026-10-24)

## Incident and evidence

`DESKTOP-5FVJMET`, project `kmj-calibration-pro`, reported:

- `PUBLIC_AGENT_AUTH_CHALLENGE=PASS`
- `ENROLLMENT_STAGE=REQUEST_CREATED`
- `Enrollment failed: CODEBRIDGE_GATEWAY_UNAVAILABLE`
- No local `agent.json` or `enrollment.json`, Home Office gateway `READY=NO`

A Windows install succeeded at CodeBridge SHA `4b6eee169b057451d3e512cd0197be08879bf8f6`. No credentials were exported. Both projectors are ON but no scan is approved.

The **observed live** Laravel release, `platform-8070dad72c55` (source SHA `8070dad72c551e5e13d1a78b0d4e6933c2d2ae9b`), uses **`services.codebridge_gateway.url`** for the device enrollment response. This is the old private MCP upstream, which can be a loopback origin. A loopback URL cannot be a remote Windows agent's public HTTPS endpoint. The newer source separates `CODEBRIDGE_AGENT_PUBLIC_URL` and validates it before credential issuance (PRs #537 and #547). **Merged source is not proof of deployment.** Exact live env/cache cause is still not independently measured.

## Guarded operator sequence

1. **No further owner pairing or revocation** while server configuration is unhealthy. Never invent or copy bearer tokens.
2. Inspect live release pointer, Nginx/PHP readiness, a restorable encrypted backup and the approved release manifest. The latest observed supervisor evidence says `currentRelease=platform-8070dad72c55`, `expectedCurrentRelease=platform-54142f844c0b`, `readyToActivate=false`. **Do not bypass the pointer mismatch or activate an unapproved SHA.** Reconcile through the operator's protected manifest/guarded rollout procedure, not by changing CodeBridge tool arguments.
3. In the intended new release, the **private** `CODEBRIDGE_GATEWAY_URL` stays pointed at the authenticated server-side MCP/agent upstream. The **public** `CODEBRIDGE_AGENT_PUBLIC_URL` must be separately configured as the exact externally reachable canonical HTTPS origin, `https://kmjtechno.com`, only after origin, routes and auth are independently verified. Do not use `http://127.0.0.1` for the public URL or silently alias/fallback from the private upstream.
4. Clear/rebuild Laravel cached configuration only under approved safeguarded deployment. Without executing any mutation, run `php artisan codebridge:agent-origin-doctor` **from the candidate release after its source and config are effective**. It must report `CODEBRIDGE_PAIRING_CONFIG=PREFLIGHT_PASS_NOT_DEVICE_READY`. This read-only doctor never claims the agent is connected, prints no URLs/config values/tokens, and sends only one anonymous fixed-origin `POST /agent/health` to establish HTTP 401.
5. Verify live release pointer/health and authenticated owner browser QA. Only then request a new owner-approved Home Office pairing when there is no recovered local credential and **only** the exact stale Home Office device has been explicitly revoked by the owner. Use the pinned, separate CodeBridge runtime, and confirm local `ENROLLMENT_STAGE=APPROVAL_RECEIVED`, `ENROLLMENT_STAGE=PRIVATE_GRANT_SAVED`, `HOMEOFFICE_PAIR=OWNER_APPROVED_PRIVATE_ENROLLMENT_SAVED`, then a fresh authenticated heartbeat. An owner click or HTTP 401 preflight is **not** agent READY.
6. Verify `connection_overview(device=kmj-homeoffice-desktop-5fvjmet, project=kmj-calibration-pro)` says `READY`. Only then trigger the allowlisted `calibration_v4_qa:full` profile if present, and begin physical projector blackout/isolation, CP Plus fisheye preflight and held-out geometry tests after explicit hardware safety authorization.

## Software-only acceptance and limits

- Unit tests `CodeBridgeAgentOriginDoctorTest` use HTTP fakes, proving fail-closed config, no secrets, no cross-domain contact, and no connection-status spoofing.
- This is a **diagnostic and runbook**, not an unconditional release tool. It does not set environment variables, modify production, rotate credentials, restart Nginx/PHP, touch DNS, change databases, or operate projectors/cameras.
- Never claim end-to-end calibration quality or one-shot accuracy until exact hardware receipts demonstrate held-out error and independently measured overlap/coverage.
