# KMJ TECHNO | First-party P520 CodeBridge connection.
# Delivery and enrollment use only kmjtechno.com. No package download or GitHub network calls.
# Existing trusted PINNED local runtime is reused. This cannot bypass owner approval.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$origin = 'https://kmjtechno.com'
$hostName = 'DESKTOP-5FVJMET'
$deviceId = 'kmj-homeoffice-desktop-5fvjmet'
$projectId = 'kmj-calibration-pro'
$runtimeCommit = '0a1fcd6804a70e915ecf66df0d4a7786f5270f02'
$launcherRelative = 'scripts\windows\ONE-CLICK-AGENT-AUTOCONNECT.ps1'
$allowedOrigins = @(
    'https://github.com/kmjtechno/kmj-codebridge.git',
    'https://github.com/kmjtechno/kmj-codebridge',
    'git@github.com:kmjtechno/kmj-codebridge.git'
)

function Fail([string]$Reason) {
    Write-Output ('KMJ_DOMAIN_CONNECT=BLOCKED:' + $Reason)
    Write-Output ('DEVICE=' + $deviceId)
    Write-Output ('PROJECT=' + $projectId)
    exit 2
}
function Normal([string]$Value,[bool]$Directory) {
    $item = Get-Item -LiteralPath $Value -ErrorAction Stop
    if ([bool]$item.PSIsContainer -ne $Directory) { throw 'PATH_TYPE_MISMATCH' }
    $cursor = if ($Directory) { $item } else { $item.Directory }
    while ($null -ne $cursor) {
        if ($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'REPARSE_POINT_DENIED' }
        $cursor = $cursor.Parent
    }
}
try {
    if ($env:OS -cne 'Windows_NT') { Fail 'WINDOWS_REQUIRED' }
    if ($env:COMPUTERNAME -ine $hostName) { Fail 'WRONG_WINDOWS_HOST' }
    $uri = $origin + '/api/codebridge/v1/device-enrollments/readiness'
    try {
        $res = Invoke-WebRequest -UseBasicParsing -Uri $uri -Method Get -MaximumRedirection 0 -TimeoutSec 15 -Headers @{Accept='application/json';'Cache-Control'='no-cache'}
    } catch [System.Net.WebException] {
        $code = if ($null -ne $_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { 0 }
        if ($code -eq 404) { Fail 'SERVER_UPDATE_REQUIRED_404' }
        if ($code -eq 503) { Fail 'PAIRING_CONFIG_NOT_READY_503' }
        Fail 'DOMAIN_READINESS_UNAVAILABLE'
    }
    if ([int]$res.StatusCode -ne 200) { Fail 'DOMAIN_READINESS_UNAVAILABLE' }
    $payload = $res.Content | ConvertFrom-Json -ErrorAction Stop
    if ($null -eq $payload -or [int]$payload.protocol -ne 2 -or [string]$payload.pairing_config -cne 'ready') {
        Fail 'DOMAIN_PAIRING_CONTRACT_NOT_READY'
    }
    # An anonymous POST must be rejected with 401 by the actual agent gateway.
    try {
        $null = Invoke-WebRequest -UseBasicParsing -Uri ($origin + '/agent/health') -Method Post -ContentType 'application/json' -Body '{}' -MaximumRedirection 0 -TimeoutSec 15
        Fail 'PUBLIC_AGENT_AUTH_NOT_ENFORCED'
    } catch [System.Net.WebException] {
        if ($null -eq $_.Exception.Response -or [int]$_.Exception.Response.StatusCode -ne 401) {
            Fail 'PUBLIC_AGENT_ROUTE_NOT_READY'
        }
    }
    $git = (Get-Command git.exe -ErrorAction Stop).Source
    Normal $git $false
    $roots = @()
    foreach ($parent in @('E:\KMJ','D:\KMJ-HyperSpeed')) {
        if (!(Test-Path -LiteralPath $parent -PathType Container)) { continue }
        Normal $parent $true
        $dirs = @(Get-ChildItem -LiteralPath $parent -Directory -ErrorAction Stop | Where-Object {
            $_.Name -match '^CodeBridge-HomeOffice(?:-[a-fA-F0-9-]+)?$' -and
            -not ($_.Attributes -band [IO.FileAttributes]::ReparsePoint)
        } | Select-Object -First 20)
        foreach ($candidate in $dirs) {
            $root = $candidate.FullName
            $launch = Join-Path $root $launcherRelative
            if (!(Test-Path -LiteralPath $launch -PathType Leaf)) { continue }
            try {
                Normal $root $true
                Normal $launch $false
                $originUrl = [string]((& $git -c core.fsmonitor=false -C $root remote get-url origin 2>$null) | Select-Object -First 1)
                if ($LASTEXITCODE -ne 0 -or $originUrl.Trim() -cnotin $allowedOrigins) { continue }
                $rev = [string]((& $git -c core.fsmonitor=false -C $root rev-parse HEAD 2>$null) | Select-Object -First 1)
                if ($LASTEXITCODE -ne 0 -or $rev.Trim() -cne $runtimeCommit) { continue }
                $tracked = @(& $git -c core.fsmonitor=false -C $root ls-files --error-unmatch -- $launcherRelative 2>$null)
                if ($LASTEXITCODE -ne 0 -or $tracked.Count -ne 1) { continue }
                $dirty = @(& $git -c core.fsmonitor=false -c core.untrackedCache=false -C $root status --porcelain=v1 --untracked-files=no 2>$null)
                if ($LASTEXITCODE -ne 0 -or $dirty.Count -ne 0) { continue }
                $roots += $root
            } catch { continue }
        }
    }
    if ($roots.Count -eq 0) { Fail 'PINNED_LOCAL_RUNTIME_NOT_FOUND' }
    if ($roots.Count -gt 1) { Fail 'MULTIPLE_PINNED_RUNTIMES_NEED_REVIEW' }
    $script = Join-Path $roots[0] $launcherRelative
    Write-Output 'KMJ_DOMAIN_ORIGIN=VERIFIED_HTTPS'
    Write-Output 'KMJ_DOMAIN_PAIRING_CONTRACT=PASS'
    Write-Output 'KMJ_DOMAIN_AGENT_AUTH=PASS'
    Write-Output 'KMJ_DOMAIN_PINNED_LOCAL_RUNTIME=PASS'
    Write-Output ('DEVICE=' + $deviceId)
    Write-Output ('PROJECT=' + $projectId)
    # Official existing wizard reuses exactly the approved HomeOffice scope.
    $systemPS = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    Normal $systemPS $false
    & $systemPS -NoProfile -STA -ExecutionPolicy RemoteSigned -File $script -Device HomeOffice
    if ($LASTEXITCODE -ne 0) { Fail 'OWNER_APPROVAL_OR_LOCAL_RECONNECT_PENDING' }
    Write-Output 'KMJ_DOMAIN_CONNECT=LOCAL_FLOW_COMPLETE_ACCOUNT_READY_MUST_BE_VERIFIED'
    Write-Output 'CREDENTIALS_EXPORTED=NO'
    exit 0
} catch {
    Fail 'PREFLIGHT_FAILED_CLOSED'
}
