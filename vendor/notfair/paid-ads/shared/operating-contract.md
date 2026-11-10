# Paid Ads Operating Contract

Read this before any paid-media analysis, recommendation, or mutation. For live NotFair work, follow [`../../docs/mcp-connection.md`](../../docs/mcp-connection.md). Choose tools from the live connection and verify the requested platform and account. Keep reads and changes within their declared capability boundaries.

## Evidence and money

1. Read the connected account, supplied export, or source artifact before making a recommendation. State the source, currency, date window, attribution model, and denominator beside every material metric.
2. Verify conversion tracking before declaring a CPA, ROAS, or waste finding actionable. If tracking is unverified, frame performance conclusions as provisional.
3. Show the current state, proposed state, daily and implied monthly spend, scope, and expected observation window before a change that can affect delivery or spend.
4. Obtain explicit approval for every spend-increasing action, campaign enablement, budget change, bid change, or irreversible deletion. Create campaigns paused where the connected platform supports creation; never assume that a plan is live.
5. Use capabilities whose current contract supports the requested change. Read the changed entity back and report the confirmed result, including any partial failure.
6. Prefer the narrowest reversible intervention. Change one material variable at a time unless the user approves a bundled, clearly itemized operation.

## Capability boundary

NotFair currently exposes first-party MCP operating surfaces for Google Ads, Meta Ads, X Ads, LinkedIn Ads, Reddit Ads, and TikTok Ads. Route live work to the platform skill instead of recreating its procedures:

| Need | Use |
|---|---|
| Google Ads account setup, audit, management, copy, assets, or landing-page diagnosis | `/notfair:google-ads-audit`, `/notfair:google-ads`, `/notfair:google-ads-copy`, `/notfair:google-ads-assets`, or `/notfair:google-ads-landing` |
| Meta account setup, audit, management, or creative briefs | `/notfair:meta-ads-audit`, `/notfair:meta-ads`, or `/notfair:meta-ads-creative` |
| X Ads account analysis, campaigns, line items, targeting, creative, audiences, or mutations | `/notfair:paid-ads-x` |
| LinkedIn Ads account analysis, campaign groups, campaigns, creatives, targeting, conversions, leads, or mutations | `/notfair:paid-ads-linkedin` |
| Reddit Ads account analysis, campaigns, ad groups, ads, targeting, audiences, pixels, or mutations | `/notfair:paid-ads-reddit` |
| TikTok Ads account analysis, delivery entities, targeting, creative, or mutations | `/notfair:paid-ads-tiktok` |

For Amazon and ChatGPT Ads, this plugin does not currently declare a NotFair MCP mutation surface. Treat those skills as planning and evidence-review workflows unless the current session exposes a verified connector. Never invent tool names, account access, platform limits, or a published campaign. Ask for an export, a read-only connector, or a human operator in the platform UI when needed.

## Reviewable artifacts

Use the following statuses consistently:

- `draft` — needs a decision or missing evidence.
- `ready_for_review` — sufficiently specified for a user or operator to approve.
- `approved_to_publish` — the user approved the exact scope; still verify connector capability before attempting publication.
- `published` — read back from a verified platform surface.

Do not call a brief, recommendation, or generated asset published.
