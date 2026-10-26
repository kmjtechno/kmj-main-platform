# CodeBridge — First-party Windows connection from Main Platform

User workflow, from the authenticated `/services/kmj-codebridge` dashboard:

1. In **Devices & projects** or **Setup & integrations**, select **Connect Windows PC**. The download is served by **kmjtechno.com** at `/install-codebridge-windows.cmd`; users need not open GitHub or type a PowerShell command.
2. On that Windows PC, double-click the downloaded file and approve normal OS download warnings after verifying it came from the KMJ domain. Its script is fetched from the same KMJ origin and **verified by a SHA-256 hash embedded in the downloaded CMD** before execution.
3. Git and Node.js 24+ with npm are required. The bootstrap first reuses an **already installed Node 24+** on PATH, then checks bounded known `%LOCALAPPDATA%\\KMJ-CaliPro\\toolchains\\node*` locations for the existing Home Office portable LTS. It modifies its **own process PATH only**, never the machine/user PATH or PowerShell policy. It does not silently install prerequisites.
4. The bootstrap fetches reviewed CodeBridge commit `9c35bdbe999f702a6c19fde22c7baeefa3c8894f` (**CodeBridge CI PASS**), checks source origin, HEAD, tracked cleanliness, and installs frozen npm dependencies without lifecycle hooks in an isolated per-user application-data directory. It never updates or cleans an existing owner checkout.
5. **Home Office P520** (`DESKTOP-5FVJMET`) is recognized automatically; it launches the exact audited `ONE-CLICK-AGENT-AUTOCONNECT.ps1 -Device HomeOffice` for **`kmj-homeoffice-desktop-5fvjmet / kmj-calibration-pro`**, reusing its existing private enrollment when present. It never opens a generic project picker on that PC, chooses a P720 ID, copies device tokens or registers a second project. First-time pairing still requires explicit browser approval on the **same KMJ website** at `/codebridge/pair`. **Other Windows computers** continue through the generic authorized-device picker and short-lived owner consent.
6. Once the P520 approved agent starts successfully, its audited current-user Startup shortcut provides automatic reconnect on the next Windows sign-in, without admin rights. Other supported devices may enable the same current-user behavior. Refresh the dashboard for registrations, but independently verify a **real authenticated gateway heartbeat**; registration is **not** a live online claim.

## Platform/agent limits

- First-party download is a **Windows bootstrap**, not remote desktop control. A browser cannot start an agent on an unreachable, sleeping, or unenrolled PC. Do not label a device READY without an authenticated gateway heartbeat.
- Existing Main Platform controls support tenant-scoped registration, pending device-code approval, project requests (not automatic filesystem access), credential revocation with confirmation, OAuth grant revocation, license/usage visibility and provider settings. Some of these are on adjacent routes on the same KMJ domain; the CodeBridge dashboard is the starting control surface.
- Gateway live presence, fully dashboard-driven remote agent start/stop, permission changes on active local checkouts, signed self-updating installers, offline install, Linux/macOS device package parity, audited command/job panels and tenant-filtered live events are **follow-on** backend features. No fake buttons should imply these are available.
- This change **does not deploy** Main Platform production or trigger production DNS changes. CI, exact-head test checks and owner browser QA remain required before rollout.
- The launcher uses no saved OAuth bearer, device secret, GitHub login prompt, global script execution-policy bypass, privileged task, unrestricted remote shell, or new paid infrastructure. Source repository access for the pinned public CodeBridge commit happens inside the bootstrap, not in the user's browser.

## Release maintenance

The static agent commit SHA lives in `resources/codebridge/install-windows-device.ps1`. Update the pin by audited PR only, after matching CodeBridge exact-head CI. The first-party CMD embeds the current script's SHA-256 at download time; never return an unpinned script with a mutable main-branch executable URL.

## Production pairing gate (2026-10-26)

This dashboard/installer improvement is **merged source only after CI**, not a live production deployment. The actual P520 installation already succeeded using the dedicated reviewed ZIP; its first-pairing attempt failed with `PAIRING_SERVER_FIX_NOT_LIVE` because production `GET /api/codebridge/v1/device-enrollments/readiness` was HTTP 404. The Main Platform supervisor independently reports `currentRelease=platform-8070dad72c55`, stale approval expected pointer `platform-54142f844c0b`, `readyToActivate=false`. **Do not pair repeatedly, bypass compatibility checks, overwrite release approval, change DNS or claim P520 online.** Resolve the existing isolated exact-SHA release/backup/rollback/authenticated owner QA gates first, deploy safely and verify readiness returns protocol 2 + protected `/agent/health` 401 before one new owner-approved P520 pairing.

The first-party Windows connector is deliberately available only after the Main Platform candidate is deployed: a GitHub merge alone does not update the website or its download route. P720 remains offline by owner choice.
