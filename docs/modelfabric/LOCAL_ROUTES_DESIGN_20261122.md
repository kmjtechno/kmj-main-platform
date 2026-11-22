# ModelFabric owner-operated local routes: design (source of truth for the next slice)

Status: design only, 2026-11-22. No code, no endpoint and no model is approved by this document. It implements
the third route class of ADR-004 revision 2 (owner-operated local) without weakening the SSRF guard.

## Key decision: local models are reached through a public HTTPS hostname, never a private address

`EndpointGuard` already requires HTTPS on 443, a hostname (never an IP literal), an approved host list and
public DNS answers only. A model served on the owner's own PC is therefore reachable only through a tunnel or
reverse proxy that gives it a public HTTPS hostname (for example a Cloudflare Tunnel or Tailscale Funnel the
owner runs). That keeps the guard unchanged: **no private-range exception, no IP literal, no request-supplied
URL.** A local route is an ordinary provider whose host the owner has put on the approved list, plus a route
class that adds limits.

Rejected: allowing RFC1918 or loopback targets. That is an SSRF primitive for every tenant and cannot be made
safe by a flag.

## What a local route adds on top of a normal provider

1. `cost_class = local`, set only by the owner with an attestation that the machine is theirs, that serving it
   costs KMJ nothing extra and that it is not the production host or its database.
2. Hard limits enforced in the gateway before any call: a maximum concurrent requests per route (default 1), a
   per-request timeout (default 60 s) and a daily request cap. A missing limit fails closed, exactly like a
   missing credit-cap.
3. Local routes sort after free cloud routes by default and sink while the device is unhealthy, so a sleeping PC
   never delays an answer: a failed or timed-out local call goes straight to the next route.
4. Private-source work (Groq services agreement 8.1 and similar) may use a local route only with the existing
   per-token private-source flag plus explicit owner approval; the model licence evidence is stored as a URL.
5. Evidence expires within 30 days and is revocable like every other approval. `NO_FREE_ROUTE_AVAILABLE` still
   means no route qualifies.

## Safety requirements for the implementation PR

- Reuse `ProviderManager` and `EndpointGuard` unchanged; add no new HTTP client path.
- Concurrency uses an atomic cache lock keyed by route id with a short TTL so a crashed request cannot hold it.
- The endpoint's bearer key is the provider key already stored encrypted; nothing is logged.
- Feature tests: refuses a missing or zero limit, refuses a private-IP hostname, respects the concurrency lock,
  falls through on timeout, never routes a revoked or expired local approval, never admits a tenant URL.
- Owner UX: one "Add local model" form showing the three attestations and a copy-ready tunnel checklist.

## Owner prerequisites (not code)

A separate machine that is allowed to run a model, a tunnel with a stable public HTTPS hostname, a model whose
licence permits the use, and an API key protecting the endpoint. None of these exist yet; no route is routable
until the owner supplies them and approves the route.
