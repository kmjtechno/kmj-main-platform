# KMJ TECHNO | INNOVATE | BUILD | SCALE
# First-party, credential-free Windows CodeBridge bootstrap.
# Delivered by kmjtechno.com; source is pinned and locally verified.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$pin = '9dc0ae25648c33a62631fdd35068e6b60820637d'
$origin = 'https://github.com/kmjtechno/kmj-codebridge.git'
$root = Join-Path $env:LOCALAPPDATA 'KMJ-CodeBridge\runtime'
$dest = Join-Path $root ('codebridge-' + $pin.Substring(0,12))

function SafeDirectory([string]$Path) {
    if (!(Test-Path -LiteralPath $Path -PathType Container)) { throw 'KMJ_RUNTIME_DIRECTORY_MISSING' }
    $current = Get-Item -LiteralPath $Path -ErrorAction Stop
    while ($null -ne $current) {
        if ($current.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw 'KMJ_RUNTIME_LINKED_DIRECTORY_BLOCKED'
        }
        $current = $current.Parent
    }
}

try {
    if ($env:OS -cne 'Windows_NT') { throw 'KMJ_WINDOWS_REQUIRED' }
    if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) { throw 'KMJ_USER_PROFILE_REQUIRED' }
    $git = (Get-Command git.exe -ErrorAction Stop).Source
    $node = (Get-Command node.exe -ErrorAction Stop).Source
    $npm = (Get-Command npm.cmd -ErrorAction Stop).Source
    $nodeVersion = [string](& $node --version)
    if ($LASTEXITCODE -ne 0 -or $nodeVersion -notmatch '^v([0-9]+)\.' -or [int]$Matches[1] -lt 24) {
        throw 'KMJ_NODE24_REQUIRED'
    }

    if (!(Test-Path -LiteralPath $root)) {
        New-Item -ItemType Directory -Path $root -ErrorAction Stop | Out-Null
    }
    SafeDirectory $root

    if (!(Test-Path -LiteralPath $dest)) {
        $stage = Join-Path $root ('staging-' + [guid]::NewGuid().ToString('N'))
        try {
            Write-Host 'KMJ_SETUP=FETCHING_PINNED_RUNTIME'
            & $git clone --filter=blob:none --no-checkout $origin $stage
            if ($LASTEXITCODE -ne 0) { throw 'KMJ_RUNTIME_CLONE_FAILED' }
            SafeDirectory $stage
            & $git -C $stage fetch --no-tags --depth 1 origin $pin
            if ($LASTEXITCODE -ne 0) { throw 'KMJ_RUNTIME_PIN_FETCH_FAILED' }
            & $git -C $stage checkout --detach $pin
            if ($LASTEXITCODE -ne 0) { throw 'KMJ_RUNTIME_PIN_CHECKOUT_FAILED' }
            if (Test-Path -LiteralPath $dest) { throw 'KMJ_RUNTIME_RACE_BLOCKED' }
            Move-Item -LiteralPath $stage -Destination $dest -ErrorAction Stop
        } finally {
            # Delete only this invocation's fresh staging directory, never an owner checkout.
            if (Test-Path -LiteralPath $stage) {
                SafeDirectory $stage
                Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction Stop
            }
        }
    }
    SafeDirectory $dest
    $actualOrigin = [string]((& $git -C $dest remote get-url origin 2>$null) | Select-Object -First 1)
    $actualHead = [string]((& $git -C $dest rev-parse HEAD 2>$null) | Select-Object -First 1)
    $changes = @(& $git --no-optional-locks -C $dest status --porcelain=v1 --untracked-files=no)
    if ($actualOrigin -cne $origin -or $actualHead -cne $pin -or $changes.Count -ne 0 -or $LASTEXITCODE -ne 0) {
        throw 'KMJ_RUNTIME_UNTRUSTED_OR_MODIFIED'
    }
    $connector = Join-Path $dest 'scripts\windows\ONE-CLICK-ANY-DEVICE.ps1'
    if (!(Test-Path -LiteralPath $connector -PathType Leaf)) { throw 'KMJ_CONNECTOR_MISSING' }
    $deps = Join-Path $dest 'node_modules\zod\package.json'
    if (!(Test-Path -LiteralPath $deps -PathType Leaf)) {
        Write-Host 'KMJ_SETUP=INSTALLING_LOCKED_DEPENDENCIES'
        Push-Location $dest
        try {
            & $npm ci --omit=dev --ignore-scripts --no-audit --no-fund
            if ($LASTEXITCODE -ne 0) { throw 'KMJ_DEPENDENCIES_INSTALL_FAILED' }
        } finally { Pop-Location }
        if (!(Test-Path -LiteralPath $deps -PathType Leaf)) { throw 'KMJ_DEPENDENCIES_MISSING' }
    }
    Write-Host 'KMJ_SETUP=STARTING_APPROVED_DEVICE_CONNECT'
    Write-Host 'Existing device: choose YES. New device: choose NO, then approve in your KMJ browser.'
    & $connector
    if (!$?) { throw 'KMJ_DEVICE_CONNECTION_NOT_VERIFIED' }
    Write-Host 'KMJ_SETUP=LOCAL_CONNECT_COMPLETED'
    Write-Host 'ACCOUNT_READY=CHECK_AUTHENTICATED_GATEWAY_STATUS'
} catch {
    $errorCode = [string]$_.Exception.Message
    if ($errorCode -notmatch '^KMJ_[A-Z0-9_]{3,100}$') { $errorCode = 'KMJ_SETUP_PREFLIGHT_FAILED' }
    Write-Host ('KMJ_SETUP=BLOCKED:' + $errorCode)
    Write-Host 'No credentials or owner source files were changed.'
    Write-Host 'If Git or Node.js 24 is missing, install it from its official source and retry.'
    exit 2
}
