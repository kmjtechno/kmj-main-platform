# Bounded engineering and browser QA

KMJ adopts selected engineering practices from [Superpowers](https://github.com/obra/superpowers) and [gstack](https://github.com/garrytan/gstack). Both projects publish MIT licenses. This integration is original KMJ code inspired by their methods, not an installation or vendored copy of either complete plugin. Upstream auto-update hooks and external model wrappers are not enabled.

## What runs automatically

- The existing VPS worker consumes owner-approved `autonomous-safe` issues. An empty queue makes no task-generation call.
- A task may declare up to three existing documentation or frontend source files. The worker refreshes its branch before reading them and sends at most 24,000 source bytes to the verified-free cloud model. It does not crawl the repository or supply credentials.
- The same generation request checks acceptance criteria, root cause for bug fixes, reuse and patch scope. This is a self-review, not an independent reviewer model. One format-repair attempt remains the limit.
- Declared files that overlap open work are deferred before AI generation. A proposed patch outside the declaration is blocked before application. Missing, oversized, hidden or symlinked context is rejected.
- Existing patch validation, local checks, prepared-commit recovery and required CI remain authoritative. User-provided test suggestions are never executed as arbitrary shell commands.
- Staging deployment now captures six browser samples: home, monitor and login at desktop and mobile widths. It saves screenshots, HTTP status, uncaught JavaScript exception counts, layout-overflow warnings and navigation timings in a three-day Actions artifact. This browser step uses no LLM.

## Task format

Use a precise acceptance criterion and list only the existing files needed for the change:

```markdown
## Task files
- `apps/platform/resources/js/components/nav-main.tsx`

## Acceptance
Expose the active navigation link as the current page to screen readers.
Keep its visual appearance and all other behavior unchanged.
```

Only `.md`, `.tsx`, `.ts` and `.css` under `docs/` or `apps/platform/resources/js/` are accepted as automatic file context. Older approved tasks without this section retain their existing issue-only behavior. Sensitive internal documentation must not be queued for external inference.

## Evidence and limitations

In the staging deploy run, open the `staging-qa-<run-id>` artifact. `report.json` names each screenshot and the expected deployment commit; the separate monitor verification proves the actual deployed commit. Fatal QA checks cover blank pages, missing expected content, unexpected navigation, HTTP failure and uncaught JavaScript exceptions. Horizontal overflow is advisory so an initial measurement does not create an arbitrary release threshold.

Navigation timings are a repeatable initial measurement, not field Core Web Vitals or a proven speed improvement. Compare equivalent runs before claiming a gain. Screenshots cover public staging pages with no login credentials; authenticated access continues to use the existing server-side smoke checks. This does not replace a complete functional, accessibility or security audit.

GitHub currently requires native workflow approval for PRs opened by `GITHUB_TOKEN`. The owner must select **Approve workflows to run** on such a PR before CI and merge can proceed. These practices do not remove that control, supply free inference, replenish ChatGPT limits or invent new tasks when the approved queue is empty.

## Source methods reviewed

- Superpowers: [systematic debugging](https://github.com/obra/superpowers/blob/main/skills/systematic-debugging/SKILL.md), evidence before completion and bounded implementation plans. Adapted as a short single-call prompt and deterministic scope checks; no new subagent loop.
- gstack: [report-only browser QA](https://github.com/garrytan/gstack/blob/main/qa-only/SKILL.md) and before/after performance evidence. Adapted to the existing pinned Chrome runtime through a private debugging pipe, without Bun, external browser services, model wrappers or a new browser download.
- Licenses: [Superpowers MIT](https://github.com/obra/superpowers/blob/main/LICENSE), [gstack MIT](https://github.com/garrytan/gstack/blob/main/LICENSE).

Cloud-only verified-zero inference, one authoritative writer and owner-gated critical operations remain unchanged. KMJ Cloud Nexus is a separate project.
