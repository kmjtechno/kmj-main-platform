$ErrorActionPreference = "Stop"
$base = $env:KMJ_CONTROLLER_URL
if (-not $base) { throw "Set KMJ_CONTROLLER_URL to your Render controller URL." }
Invoke-RestMethod -Method Post -Uri "$base/start" -ContentType "application/json" -Body '{"requested_by":"owner-mobile","dry_run":true}'
