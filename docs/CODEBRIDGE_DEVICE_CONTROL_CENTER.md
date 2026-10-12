# KMJ CodeBridge Main Platform Device Control Center

The authenticated service page `/services/kmj-codebridge#codebridge-device-control` provides mobile-friendly searchable registered device/project cards and quick workflows for the existing KMJ pairing, Windows/Linux installers, OAuth connection, and account security.

## Accurate state
Main Platform currently stores **registrations**, not authoritative live gateway heartbeats. Never paint an online/active badge merely because a credential exists. `connection_overview` in the connected CodeBridge MCP client is the correct live-state diagnostic. Devices are tenant-scoped, bounded at 100 rows, and no tokens or private project contents are returned.

## Disconnect protocol
A fresh, confirmed manager request to `POST /services/kmj-codebridge/organizations/{tenantId}/devices/{deviceId}/disconnect` requires standard verified-account web auth, *recent password confirmation*, CSRF protection, an actual matching device ID typed by the operator, strict identifier validation, organization manager authority, and a credential joined to the exact tenant-bound `KMJ_CODEBRIDGE` license. The existing transactional credential revoke service writes a single audit event; repeats are idempotent. A different tenant/device cannot be touched even if its ID is known.

This is **credential revocation**, not remote shutdown, OS deletion or immediate termination of already-established gateway sessions. Gateway enforcement depends on credential revalidation; future authenticated introspection calls reject revoked credentials. A formerly revoked device must initiate **new short-lived pairing** to reconnect; no button can safely resurrect a prior bearer token.

## Follow-on milestones
- Authenticated independent gateway heartbeat/last-seen aggregation with server-side bounded TTL, strict tenant grants and fail-closed unknown status
- Project grant approval/revoke/permission changes with explicit security receipts and stale-lease denial
- Multi-device pagination, tags/groups, bounded audit timeline, dashboard health and scoped jobs, status notifications and mobile device install handoff
- Native one-click desktop agent recovery and appropriate rollback, without reading tokens from the browser
- Isolated staging and exact-head CI before live deployment. No production changes are performed by this PR.
