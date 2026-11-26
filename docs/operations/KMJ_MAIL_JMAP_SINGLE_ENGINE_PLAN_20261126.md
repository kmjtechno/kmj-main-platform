# KMJ Mail — single-engine JMAP integration plan (2026-11-26)

Status: PLAN ONLY, written for the joint Claude + ChatGPT mail lane. No production, MX, DNS, Postfix or secret change is made or implied. TCP 25 ingress and engine PR4 are owned by the ChatGPT mail lane and are not touched here.

## What already exists in source (read from main, not run live)
- Read-only JMAP stack under `apps/platform/app/Services/Mail/`: `JmapMailboxContract` (session validation), `JmapReadOnlyTransport`, `JmapInboxQuery`, `JmapInboxMetadata`, `JmapMailboxResponse`, `JmapOwnerPilot`.
- One owner-only route: `POST operator/mail/jmap/inbox` (`kmj-mail.jmap-inbox`), throttled 4/min, served by `JmapOwnerInboxController`.
- The pilot is gated by config `kmj-mail-engine.pilot_enabled` and a single `pilot_owner_id`, and re-reads current owner authority on every call.
- Doc `KMJ_MAIL_ENGINE_REUSE_20261125.md` states: pure validator and request builder, no HTTP from the contract, strict origin policy that must not be weakened.

## Not proven
Live JMAP session against the real engine, per-user identity, response-size bounds under real data, owner password/passkey re-confirmation on the route, and any external delivery. Existing source is not evidence that any of these work.

## Single-authority rule
Exactly one engine is authoritative for mailboxes at a time. The Main Platform keeps ownership of identity, entitlement and audit; the engine owns message storage. No second writer, no duplicate delivery path, and no MX change until the gates below pass.

## Proposed slices (each its own small PR, exact-head CI, no deploy)
1. Contract audit: list every config key and route the JMAP path touches; add a static test that the origin allowlist rejects redirects, HTTP and foreign hosts.
2. Transport hardening tests: TLS required, redirects rejected, response size bounded, method-response account id checked, token never serialized (extend `JmapReadOnlyTransportTest`).
3. Authorization: require recent password/passkey confirmation on the route (the pilot docblock already requires it) with a failing-first test.
4. Qualification (owner-run, read-only): authenticated session discovery with synthetic data on the isolated engine; record the receipt.
5. Per-user identity mapping and audit events, still read-only.
6. Only then: write paths (send, move), after independent external SMTP/TLS/relay proof and owner gates.

## Gates before any MX or production switch
External TCP 25 reachability proven from outside; anti-relay proof; SPF, DKIM, DMARC pass on a real inbox; queue and restore recovery drill for the engine data; owner approval of the exact SHA. Each is evidence the owner or an independent test must produce; none is claimed here.

## Risks
Two engines both accepting mail (duplicate delivery); weakening the origin policy to make a pilot work; logging JMAP tokens; treating a zero Postfix queue as delivery proof.
