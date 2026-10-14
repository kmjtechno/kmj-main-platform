# KMJ CodeBridge — isolated Lenovo P720 OmniDesk agent setup.
# Normal Windows user, one project per free agent, no changes to other agents.
param([switch]$VerifyOnly)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$base = 'D:\KMJ-HyperSpeed'
$project = Join-Path $base 'projects\kmj-omnidesk'
$runtime = Join-Path $base 'projects\kmj-codebridge'
$private = Join-Path $base 'private\p720-omnidesk'
$state = Join-Path $private 'state'
$logs = Join-Path $private 'logs'
$conf = Join-Path $private 'agent.json'
$enrollment = Join-Path $private 'enrollment.json'
$report = Join-Path $base 'P720-OMNIDESK-ONBOARDING-STATUS.txt'
$projectId = 'kmj-omnidesk'
$deviceId = 'kmj-omnidesk-' + ($env:COMPUTERNAME -replace '[^A-Za-z0-9_-]', '-').ToLowerInvariant()
if ($deviceId.Length -gt 64) { $deviceId = $deviceId.Substring(0,64) }
function Require([bool]$ok, [string]$message) { if (-not $ok) { throw $message } }
function Status([string]$kind, [string]$message) {
    $line = ('{0}: {1}' -f $kind, $message)
    Write-Host $line
    Add-Content -LiteralPath $report -Value $line -Encoding UTF8
}
function ProtectDir([string]$dir) {
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    & icacls.exe $dir /inheritance:r /grant:r ('*' + $sid + ':(OI)(CI)F') | Out-Null
    Require ($LASTEXITCODE -eq 0) 'PRIVATE_DIR_ACL_FAILED'
}
function ProtectFile([string]$file) {
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    & icacls.exe $file /inheritance:r /grant:r ('*' + $sid + ':F') | Out-Null
    Require ($LASTEXITCODE -eq 0) 'PRIVATE_FILE_ACL_FAILED'
}
function ExistingAgent {
    @(Get-CimInstance -ClassName Win32_Process -Filter "Name = 'node.exe'" | Where-Object {
        $_.CommandLine -and $_.CommandLine.Contains($conf) -and
        $_.CommandLine -match 'src[\\/]cli\.js' -and $_.CommandLine -match '\bagent\b'
    })
}
function VerifyScope {
    Require (Test-Path -LiteralPath (Join-Path $project '.git')) 'OMNIDESK_GIT_MISSING'
    Require (-not ((Get-Item -LiteralPath $project).Attributes -band [IO.FileAttributes]::ReparsePoint)) 'PROJECT_SYMLINK_REJECTED'
    $origin = (& git.exe -C $project remote get-url origin 2>$null | Out-String).Trim()
    Require ($LASTEXITCODE -eq 0) 'GIT_ORIGIN_UNAVAILABLE'
    Require ($origin -in @('https://github.com/kmjtechno/kmj-omnidesk.git', 'https://github.com/kmjtechno/kmj-omnidesk', 'git@github.com:kmjtechno/kmj-omnidesk.git')) 'OMNIDESK_GIT_ORIGIN_MISMATCH'
    Require (Test-Path -LiteralPath (Join-Path $project 'Cargo.toml')) 'OMNIDESK_CARGO_MISSING'
    Require (Test-Path -LiteralPath (Join-Path $project 'ROADMAP.yaml')) 'OMNIDESK_ROADMAP_MISSING'
}
function VerifyPrivateConfig {
    $c = Get-Content -LiteralPath $conf -Raw | ConvertFrom-Json
    Require ([string]$c.gateway -in @('https://kmjtechno.com/', 'https://kmjtechno.com')) 'UNEXPECTED_GATEWAY'
    Require ([string]$c.id -ceq $deviceId) 'DEVICE_ID_MISMATCH'
    Require ([string]$c.stateDir -ceq $state) 'STATE_DIR_MISMATCH'
    Require ([string]$c.token -ne '' -and [string]$c.tenant -ne '') 'MISSING_CREDENTIAL'
    Require (@($c.projects).Count -eq 1) 'MORE_THAN_ONE_PROJECT'
    Require ([string]$c.projects[0].id -ceq $projectId -and [string]$c.projects[0].root -ceq $project) 'PROJECT_SCOPE_MISMATCH'
    Require ([string]$c.license.mode -eq 'free') 'UNEXPECTED_LICENSE_MODE'
}
try {
    Require ($env:OS -eq 'Windows_NT') 'WINDOWS_REQUIRED'
    Require (Test-Path -LiteralPath 'D:\') 'P720_D_DRIVE_REQUIRED'
    New-Item -ItemType Directory -Path $base -Force | Out-Null
    Set-Content -LiteralPath $report -Value 'KMJ OmniDesk CodeBridge setup (no credentials in report)' -Encoding UTF8
    Require ($null -ne (Get-Command git.exe -ErrorAction SilentlyContinue)) 'GIT_REQUIRED'
    Require ($null -ne (Get-Command node.exe -ErrorAction SilentlyContinue)) 'NODE_REQUIRED'
    $major = [int]((& node.exe --version).Trim() -replace '^v([0-9]+).*$', '$1')
    Require ($major -ge 24) 'NODE_24_REQUIRED'
    Require (Test-Path -LiteralPath (Join-Path $runtime 'scripts\enroll-device.js')) 'CODEBRIDGE_RUNTIME_MISSING'
    Require (Test-Path -LiteralPath (Join-Path $runtime 'node_modules\zod\package.json')) 'CODEBRIDGE_RUNTIME_DEPENDENCIES_MISSING'
    if (-not (Test-Path -LiteralPath $project)) {
        if ($VerifyOnly) { throw 'OMNIDESK_CHECKOUT_PENDING' }
        New-Item -ItemType Directory -Path (Split-Path $project -Parent) -Force | Out-Null
        & git.exe clone --quiet --branch main -- 'https://github.com/kmjtechno/kmj-omnidesk.git' $project
        Require ($LASTEXITCODE -eq 0) 'OMNIDESK_CLONE_FAILED'
    }
    VerifyScope
    Status 'PASS' 'GitHub OmniDesk origin and Rust project verified.'
    if ($VerifyOnly) {
        if (Test-Path -LiteralPath $conf) {
            VerifyPrivateConfig
            Status 'INFO' ('Existing agent processes: ' + @(ExistingAgent).Count + '; gateway connectivity still requires independent check.')
        } else { Status 'PENDING' 'Separate OmniDesk agent enrollment not yet completed.' }
        return
    }
    New-Item -ItemType Directory -Path $private, $state, $logs -Force | Out-Null
    ProtectDir $private
    ProtectDir $state
    ProtectDir $logs
    if (-not (Test-Path -LiteralPath $conf)) {
        if (-not (Test-Path -LiteralPath $enrollment)) {
            Status 'ACTION' 'Approve the requested OmniDesk pairing at the KMJ HTTPS URL displayed below.'
            & node.exe (Join-Path $runtime 'scripts\enroll-device.js') 'https://kmjtechno.com' $deviceId $projectId $project $enrollment
            Require ($LASTEXITCODE -eq 0) 'OWNER_PAIRING_NOT_COMPLETED'
        }
        ProtectFile $enrollment
        $grant = Get-Content -LiteralPath $enrollment -Raw | ConvertFrom-Json
        Require ([string]$grant.agent.id -ceq $deviceId) 'APPROVAL_DEVICE_MISMATCH'
        Require (@($grant.projects | Where-Object { $_.id -ceq $projectId }).Count -eq 1) 'APPROVAL_PROJECT_MISMATCH'
        foreach ($p in @('read','write','execute')) { Require ($grant.permissions -contains $p) 'APPROVAL_SCOPE_INCOMPLETE' }
        Require ([string]$grant.agent.token -ne '' -and [string]$grant.agent.tenant -ne '') 'APPROVAL_CREDENTIAL_MISSING'
        Require ([string]$grant.gateway -in @('', 'https://kmjtechno.com', 'https://kmjtechno.com/', 'https://kmj-codebridge-gateway.onrender.com')) 'APPROVAL_GATEWAY_UNKNOWN'
        $cfg = @{
            gateway = 'https://kmjtechno.com/'
            token = [string]$grant.agent.token
            id = $deviceId
            tenant = [string]$grant.agent.tenant
            stateDir = $state
            projects = @(@{
                id = $projectId
                root = $project
                writable = $true
                gates = @{
                    fmt = @{ command = 'cargo'; args = @('fmt','--all','--','--check'); timeoutMs = 120000 }
                    test = @{ command = 'cargo'; args = @('test','--workspace','--all-targets'); timeoutMs = 300000 }
                    clippy = @{ command = 'cargo'; args = @('clippy','--workspace','--all-targets','--','-D','warnings'); timeoutMs = 300000 }
                }
            })
            license = @{ mode = 'free' }
        }
        $bytes = (New-Object Text.UTF8Encoding($false)).GetBytes(($cfg | ConvertTo-Json -Depth 12))
        $f = [IO.File]::Open($conf, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        try { $f.Write($bytes, 0, $bytes.Length); $f.Flush() } finally { $f.Dispose() }
        ProtectFile $conf
    }
    VerifyPrivateConfig
    $existing = @(ExistingAgent)
    Require ($existing.Count -le 1) 'DUPLICATE_OMNIDESK_AGENT'
    if ($existing.Count -eq 1) {
        Status 'PASS' 'OmniDesk agent already running; no duplicate started.'
        return
    }
    $proc = Start-Process -FilePath (Get-Command node.exe).Source -ArgumentList @('src/cli.js','agent',$conf) -WorkingDirectory $runtime -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logs 'agent-out.log') -RedirectStandardError (Join-Path $logs 'agent-err.log') -PassThru
    Start-Sleep -Seconds 4
    $proc.Refresh()
    Require (-not $proc.HasExited) 'OMNIDESK_AGENT_EARLY_EXIT'
    Status 'STARTED' ('Isolated OmniDesk agent PID: ' + $proc.Id)
    Status 'PENDING' 'Check CodeBridge list_devices and inspect_project before claiming online.'
} catch {
    if (Test-Path -LiteralPath $report) { Status 'BLOCKED' ([string]$_.Exception.Message) }
    else { Write-Host ('BLOCKED: ' + [string]$_.Exception.Message) }
    exit 2
}
