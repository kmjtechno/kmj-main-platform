# KMJ CodeBridge — first-party domain-only P520 connection
Status: SOURCE ONLY; NOT DEPLOYED, NOT PUBLICLY LIVE, NOT DEVICE READY.
Scope: `DESKTOP-5FVJMET`, `kmj-homeoffice-desktop-5fvjmet` / `kmj-calibration-pro`.

## Customer experience after guarded Main Platform publication
1. Open `https://kmjtechno.com/codebridge-connect.html`.
2. Download `https://kmjtechno.com/KMJ-CodeBridge-P520-Connect.cmd` and double-click as the normal Windows user.
3. CMD fetches its pinned PowerShell script only from `https://kmjtechno.com/KMJ-CodeBridge-P520-Connect.ps1`; SHA-256 must equal `07a9478695172587f01bc28076880a845cd7b7917ec6025a13c9316abe0a3e11`. Only after matching hash is this one downloaded script unblocked under Windows RemoteSigned.
4. The script checks fixed Windows identity, exact public `GET /api/codebridge/v1/device-enrollments/readiness` contract protocol=2/pairing_config=ready and that anonymous `POST /agent/health` is rejected 401. Any 404/503/error stops without creating orphan pairing.
5. Reuse the local existing clean pinned CodeBridge source at `0a1fcd6804a70e915ecf66df0d4a7786f5270f02`; no source download, no Node installation, no credential copy, no project changes. Execute official scoped HomeOffice one-click, which requires owner approval on `https://kmjtechno.com/codebridge/pair`, never approval by this bootstrap.
6. Confirm actual account-side `connection_overview=READY`. Local process/heartbeat is not proof of a granted device.

## Critical production release gate
The currently active production release is `platform-8070dad72c55` and readiness returned HTTP 404 from the P520 launcher. Exact newer Main Platform `ad4cfa68291ec6a05e88f30ed0a93b2d15af40fe` was staged as an isolated candidate, but the owner-approved production manifest still expects prior `platform-54142f844c0b` and target-specific backup/witness are ABSENT_OR_UNSAFE. Do NOT force symlink, DNS, or manifest change. No production publication of these files has been performed.

This private working checkout is not identical to the already-built isolated release candidate. For these three new public assets to go LIVE, first integrate them into the authoritative release source, run Windows native parsing and behavioral tests plus source-only `python3 scripts/test_codebridge_domain_only_p520_20261028.py`, rebuild an immutable candidate, prove restorable current backup+rollback, reconcile protected owner approval, and activate only with the guarded release controller. First-party domain routing never replaces owner approval nor proof of live gateway authentication.

## Domain-only design extension
General device onboarding should use authenticated Main Platform customer center to select project and bind a server-granted project ID; local folder selection must remain explicit, and a project assignment request alone is not filesystem access. Existing service project assignment currently requires a GitHub repository URL; redesign and test local-only project records before offering GitHub-free arbitrary projects. Avoid using a GitHub repo as an installer/download dependency even if internal engineering source control remains permitted.
