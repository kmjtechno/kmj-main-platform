# SEO Shared Preamble

Match setup to the task. URL-only reviews and supplied exports do not require
Search Console authentication. For live Search Console work, use an available
connector and follow [`../../docs/mcp-connection.md`](../../docs/mcp-connection.md)
for NotFair. Let the connection's current instructions and schemas determine
tool selection, and confirm the intended property from live data.

## Optional local scripts

The repository also provides scripts under `seo/seo-analysis/scripts/` for
crawling, local analysis, and direct Search Console access. Locate them relative
to the installed skill directory and set `SKILL_SCRIPTS` to that directory when a
workflow uses them. Choose the script or connected capability that fits the task;
a script example in a workflow is not a requirement to replace a working MCP.

Only run `preflight.py` when the task actually needs the direct Google API script
path and its dependencies are missing. This path uses gcloud credentials and
Google Cloud setup; it is not required for NotFair MCP access. See
`../seo-analysis/references/gsc_setup.md` for that optional setup. Do not install
additional dependencies or start a second authentication flow just because an
SEO skill was invoked.

If live data is unavailable, explain the gap and continue the portions supported
by the user's URL, repository, or export. Do not present missing data as zero.
