# KMJ Main Platform read-only staging preflight (28 Oct 2026)

This inspector produces an owner-run receipt of fixed staging DNS/HTTPS-origin readiness, Nginx syntax, current release identity, and publicly visible exact deploy SHA. It **does not** issue an approval, deploy a candidate, modify a certificate/vhost, run migrations, access customer contents, or switch the production release.

Exact candidate SHA: `ad4cfa68291ec6a05e88f30ed0a93b2d15af40fe`. Previous live release: `platform-8070dad72c55`.

Revision V3 fixes a prior false-negative from Ubuntu's canonical `sites-enabled` symlink and keeps the original immutable receipt unchanged. A direct, non-secret, no-overwrite QA receipt is accessible to the project-scoped CodeBridge agent. The previous pre-staged V1 source hash must **not** be used to validate or execute this newer revision. Obtain the exact source and independent digest for V3 before root execution.

The owner/operator runs the independently SHA-256 verified source on **KMJ-elite**, with root only because it checks Nginx and localhost TLS. It emits no secrets and writes a one-time, 0644, bounded JSON receipt at `work/qa/KMJ_MAIN_PLATFORM_STAGE_PREFLIGHT_V3_20261028.json` within the CodeBridge project. Read this via the connected CodeBridge `read_files_batch` after execution. If a receipt already exists, the source refuses to overwrite it; preserve historical evidence.

The origin probe uses `staging.kmjtechno.com:443` pinned to loopback, performs normal CA and hostname verification and checks `X-KMJ-Deploy-SHA` exactly. It does **not** proxy staging through Cloudflare or disable certificate verification. This is an inspect-only QA receipt and is not itself proof of an independent offsite restore or an authenticated owner browser acceptance.

Do not alter the protected release manifest or call the activation supervisor until actual staging, owner acceptance, independent backup/rollback and exact fresh owner approval all pass. The historical V1 CodeBridge script has SHA-256 `1c83f279d520390871db078434ea83d2fb4cd4cd64fab671e4e29216ed1675c9` and is **not** interchangeable with V3. V3 must be separately staged, independently hash-verified, and owner-run. No V3 execution or live deployment is claimed by this PR. 
