# KMJ Mail Enterprise — LOCKED owner visual reference (2026-11-23)

**Source of truth:** The exact screenshot the owner supplied in the chat on
2026-11-23 at 10:37:49 UTC. The owner explicitly asked to **implement the
approved design**, not generate a new image. The screenshot is a visual layout
reference; example numbers, names, messages, connected status and model output
are NOT production evidence and must never be copied as real data.

## Fixed desktop composition (approx. 1648-pixel reference)

1. **Global owner shell:** locked KMJ TECHNO red/black wordmark, full mail search
   with Ctrl+K focus, highlighted KMJ AI, alerts, provider settings/help and
   actual owner profile. Do not create or replace the approved logo.
2. **Enterprise hero:** dark midnight background, red dotted globe/glow behind
   header, left mail icon, bright company eyebrow, KMJ Mail Enterprise title,
   security badge. Underneath: five compact live metrics in one row.
3. **Four-pane mailbox beneath hero:** narrow mail folders, message-list triage,
   real private message reader with approved wordmark, and right AI rail. AI
   rail begins at the top of the hero and spans both rows at wide desktop
   widths. Responsive stack for tablet/phone; never overflow horizontally.
4. **Left folders:** prominent red Compose, Inbox, Starred, Sent, Drafts,
   Archive, Trash. Coloured project filters derive from real search; they are
   not an invented label storage system. Spam, snoozed and important require
   additional protected data model + business process before they can be shown
   as working.
5. **Message triage:** Primary/Team/Updates/System filter tabs for the CURRENT
   page, checkboxes, real pagination, sender avatars, subject/snippet, real
   delivery status and selected row. Any category heuristic must be labelled
   and must not misstate a server-side inbox classifier.
6. **Reader:** strong subject typography, Reply/Forward/Star/Archive/Trash
   backed by existing authenticated handlers, sender and status evidence,
   locked KMJ logo, black/navy message surface and approved red accents.
7. **Floating Compose:** contained dark navy window with magenta-red border,
   recipient selector, subject, plain text body, AI entry point, minimize,
   expand, close, Save Draft and explicit user-operated Send. No automatic
   mail send, undeclared CC/BCC, MIME or attachment UI.
8. **AI Assistant:** title, Compose/Summarize/Reply/Tools tabs, Hinglish prompt,
   verified private ModelFabric request with explicit per-request consent,
   professional tone/language controls, resulting editable drafts and
   context-aware reply. Reuse user-owned mailbox content only and discard stale
   responses when conversation changes.

## Trusted data, no screenshot fiction

- Unread and total are per-user mail database counts, never global data.
- Team recipients from approved staff directory, not customers.
- Mail text usage is an approximate aggregate; NOT 50GB quota or physical disk.
- SMTP readiness is permission to queue, NOT proof that a recipient got it.
- Incoming Internet mail, attachments, Spam engine, rich MIME, CC/BCC,
  scheduled send and full-text label storage are separate work requiring
  secure integrations, opt-in and dedicated regression tests.
- AI result cards only appear after successful real inference from the
  authenticated provider. Never prepopulate sample replies as if generated.

## Delivery acceptance

Frontend TypeScript/format + Laravel authorization/metrics + static brand checks
+ 6-viewport browser tests must pass; require owner visual comparison of the
actual new release, not a new generated mockup. Merge exact HEAD only after
CI; KMJ-elite production requires SHA-pinned owner approval, Supervisor protected
activation, health receipt and post-activation migration confirmation.
