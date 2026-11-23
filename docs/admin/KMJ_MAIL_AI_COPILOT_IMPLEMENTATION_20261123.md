# KMJ Mail Enterprise AI Copilot — approved owner design (23 Nov 2026)

The approved mockup is **design direction**, not proof of connected AI models or working inbound mail. Reuse the approved KMJ TECHNO red/graphite logo and enterprise owner theme. Do not create or replace official brand assets.

## Implemented in this source candidate

- Right-side **KMJ AI Copilot** in the actual authenticated Mail Center React page, responsive below the reader on narrow viewports.
- **Write with AI** — submit Hinglish instructions, pick Professional/Formal/Friendly/Firm and English/Hindi/Hinglish, get subject + body as **an editable Compose draft**.
- **Explain in Hindi** — explain the selected private email's meaning, facts, action items and explicit deadlines in Hindi; clearly state absent deadlines.
- **Smart Reply** — build a suggested reply for the selected message; insert only when the user clicks **Use in Reply**.
- **Consent each request** to provider processing; opt-in resets on mode changes. No background inference; no automatic send, forwarding, auto-save, mail queue, provider key in browser, or mutable remote endpoint.
- Server checks operator owner or explicitly authorized team member; selected email must belong to the same user's mailbox. Validation bound to instruction length 2,000 and quoted email 6,000 chars; AI response limited to existing 12,000-char email body/180-char subject.
- Routes only through existing ModelFabric tenant scope and **private_source=true**, requiring verified-zero route plus current *no-training-documented* provider evidence. If no route, show **NO_PRIVATE_AI_ROUTE_AVAILABLE** rather than fabricated text or a hidden paid route. Does not log message bodies.
- Rate limit 4 requests/minute per existing middleware; authenticated, verified and password-confirmed, same-origin CSRF session.

## Next phases — NOT implemented by this candidate

- Actual multi-recipient, CC/BCC and MIME attachment send; storage/virus scan, configurable signatures and scheduled send.
- Real inbound MX-to-mailbox ingress, spam engine, snooze, filters, labels, AI tools/integration APIs, per-tenant AI quotas in Mail UI.
- Verified live AI provider enrollment and fresh desktop/mobile workflow acceptance.
- Provider privacy notice, retention/DPAs, prompt-injection adversarial test expansion and accessibility keyboard QA.

## Release gates

1. PHP authorization, explicit consent, mailbox isolation, no-provider fail-closed, and no-send tests PASS.
2. Full TS/React build, formatter, mobile/desktop responsive browser QA and existing auth/mail regressions PASS.
3. Merge exact PR HEAD, merged-main staging + disposable database/rollback gates PASS.
4. Owner-pinned Elite SHA prepare/approval; CodeBridge protected activation, health/readback and post-activation migration receipt.
5. Actual owner click-through for Compose/Hindi Explain/Smart Reply using a verified private zero-spend provider. Human review required before Send. Never claim AI inference passed when no admitted provider exists.
