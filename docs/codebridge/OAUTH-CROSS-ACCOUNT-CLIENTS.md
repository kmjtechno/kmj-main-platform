# CodeBridge OAuth — independent AI client and KMJ account identities

## Intended behavior

An AI client login (ChatGPT, Claude, Gemini, IDE/CLI) and a KMJ Main Platform login are **two independent identities**. Different email addresses are permitted. The KMJ user who approves the consent is the account used to issue the OAuth token. No AI-provider email is accepted by the authorization server as proof of KMJ membership.

1. Start the CodeBridge OAuth connection in the AI client for the configured resource `https://kmjtechno.com/mcp`.
2. The KMJ consent page shows the **current KMJ account** name/email, the AI client name and requested scopes.
3. If the displayed KMJ account is wrong, select **Use a different KMJ account**. This ends only the browser's current KMJ web session, consumes the old pending consent and preserves the server-validated client, registered callback, opaque state, audience and PKCE challenge.
4. Sign in to the intended KMJ account, verify the displayed identity and explicitly **Approve**. Tokens are bound to `kmj-user:<numeric id>`, issuer, the MCP resource audience, client and granted scopes—not to the AI client's email.
5. Tools still require current KMJ organization membership, an active CodeBridge license, paired device/project grants and allowed permissions. An unrelated or unlicensed KMJ account cannot access another account's projects by approving consent.
6. If approval succeeds but tools return `ACCESS_DENIED` or the user introspection returns `active:false`, inspect **KMJ account membership/license/device pairing**, not the vendor account email. Reconnect after the appropriate authorized invitation or pairing; never share a bearer token or an AI account password.

## Security controls

- Consent is tied to the KMJ user shown on the page. An account changed in another browser tab cannot approve that stale consent.
- Switch is a CSRF-protected authenticated POST bound to a 40-character session-owned request identifier; no caller-selected redirect or email is accepted.
- Only an already validated OAuth request is reconstructed for a same-origin redirect. The original consent is consumed and the old browser session invalidated; the OAuth authorization code is minted only after fresh approval.
- No changes to public OAuth redirect registration, PKCE S256, JWT issuer/audience/signatures/expiry, refresh rotation or tenant/device/project policy.
- A different AI email does **not** establish a cross-user delegation. Owners must grant a separate KMJ account its own scoped access if it needs to use a different identity.

## Release gates (do not confuse source merge with deployment)

- Run `CodeBridgeOAuthServerTest` and `CodeBridgeOAuthLinkTest` on the **exact** candidate SHA, plus PHP syntax, Pint, frontend lint and Wayfinder TypeScript.
- Negative verification: unknown request ID, mismatched browser user, reused consent, wrong redirect, wrong PKCE verifier and unauthorized tenant remain denied.
- Under an approved staging URL, check ChatGPT, Claude and Gemini separately with **different AI and KMJ email accounts** using fresh OAuth clients. Verify that the resulting subject belongs to the selected KMJ user, while the wrong-user device list is never shown.
- Production update requires a current encrypted backup, verified restore and a bounded rollback step. Record deployed commit and authenticated smoke results. **Do not mark live until these are observed.**

Source of authority: `apps/platform/routes/codebridge-oauth.php` and `apps/platform/app/Services/CodeBridge/OAuth/OAuthServer.php`. Vendor login sessions are not sent to, and must not be inferred by, the KMJ authorization server.
