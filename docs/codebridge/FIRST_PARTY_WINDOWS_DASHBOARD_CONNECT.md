# CodeBridge — First-party Windows connection from Main Platform

User workflow, from the authenticated `/services/kmj-codebridge` dashboard:

1. In **Devices & projects** or **Setup & integrations**, select **Connect Windows PC**. The download is served by **kmjtechno.com** at `/install-codebridge-windows.cmd`; users need not open GitHub or type a PowerShell command.
2. On that Windows PC, double-click the downloaded file and approve normal OS download warnings after verifying it came from the KMJ domain. Its script is fetched from the same KMJ origin and **verified by a SHA-256 hash embedded in the downloaded CMD** before execution.
3. Git and Node.js 24+ are required. The bootstrap **does not silently install system prerequisites**; it checks them and stops with a clear local error when missing.
4. The bootstrap fetches a **pinned exact CodeBridge Git commit**, checks source origin, HEAD, tracked cleanliness, and installs frozen npm dependencies without lifecycle hooks in an isolated per-user application-data directory. It never updates or cleans an existing owner checkout.
5. In the local CodeBridge wizard, choose **YES** for an existing same-PC private agent enrollment; if there are several, select its existing private `agent.json`. Choose **NO** for a new local Git project and approve the short-lived code on the **same KMJ website** at `/codebridge/pair`. This browser approval is always required for a new grant and cannot be automatically bypassed.
6. After a locally authenticated reconnect, current-user login auto-connect can be enabled by the bundled agent. Refresh the dashboard for registrations. Registration is **not** a live online claim.

## Platform/agent limits

- First-party download is a **Windows bootstrap**, not remote desktop control. A browser cannot start an agent on an unreachable, sleeping, or unenrolled PC. Do not label a device READY without an authenticated gateway heartbeat.
- Existing Main Platform controls support tenant-scoped registration, pending device-code approval, project requests (not automatic filesystem access), credential revocation with confirmation, OAuth grant revocation, license/usage visibility and provider settings. Some of these are on adjacent routes on the same KMJ domain; the CodeBridge dashboard is the starting control surface.
- Gateway live presence, fully dashboard-driven remote agent start/stop, permission changes on active local checkouts, signed self-updating installers, offline install, Linux/macOS device package parity, audited command/job panels and tenant-filtered live events are **follow-on** backend features. No fake buttons should imply these are available.
- This change **does not deploy** Main Platform production or trigger production DNS changes. CI, exact-head test checks and owner browser QA remain required before rollout.
- The launcher uses no saved OAuth bearer, device secret, GitHub login prompt, global script execution-policy bypass, privileged task, unrestricted remote shell, or new paid infrastructure. Source repository access for the pinned public CodeBridge commit happens inside the bootstrap, not in the user's browser.

## Release maintenance

The static agent commit SHA lives in `resources/codebridge/install-windows-device.ps1`. Update the pin by audited PR only, after matching CodeBridge exact-head CI. The first-party CMD embeds the current script's SHA-256 at download time; never return an unpinned script with a mutable main-branch executable URL.
