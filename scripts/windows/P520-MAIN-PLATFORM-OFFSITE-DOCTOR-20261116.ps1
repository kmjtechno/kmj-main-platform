# KMJ P520 Google-independent backup & Docker restore preflight (READ ONLY).
# Owner runs this on DESKTOP-5FVJMET; no file creation, backup import, key reading, or Docker container started.
# Requires PowerShell 5.1+ (Windows 10). Reports missing prerequisites but never modifies them.
[CmdletBinding()]
param([switch]$Inspect)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $Inspect) { Write-Output 'KMJ_P520_OFFSITE_DOCTOR=BLOCKED_INSPECT_ONLY'; exit 2 }
if ($env:COMPUTERNAME -ne 'DESKTOP-5FVJMET' -or $env:OS -ne 'Windows_NT') {
  Write-Output 'KMJ_P520_OFFSITE_DOCTOR=BLOCKED_WRONG_HOST'; exit 2
}
Write-Output 'KMJ_P520_OFFSITE_DOCTOR=READ_ONLY_V1'
Write-Output 'GOOGLE_VPS_DEPENDENCY=NONE'
function CmdState([string]$Name) {
  $found = Get-Command $Name -ErrorAction SilentlyContinue
  if ($null -eq $found) { return 'MISSING' }
  return 'PRESENT'
}
$commands = @('docker.exe', 'ssh.exe', 'sftp.exe', 'ssh-keygen.exe', 'openssl.exe', 'age.exe')
foreach ($cmd in $commands) { Write-Output ("TOOL_{0}={1}" -f $cmd.Replace('.exe','').ToUpperInvariant(),(CmdState $cmd)) }
$docker = Get-Command docker.exe -ErrorAction SilentlyContinue
if ($null -ne $docker) {
  $dockerOutput = @(& docker.exe info --format '{{.OSType}}' 2>$null)
  if ($LASTEXITCODE -eq 0 -and $dockerOutput.Count -eq 1 -and $dockerOutput[0] -eq 'linux') {
    Write-Output 'DOCKER_LINUX_ENGINE=PASS'
  } else { Write-Output 'DOCKER_LINUX_ENGINE=BLOCKED_NOT_RUNNING' }
} else { Write-Output 'DOCKER_LINUX_ENGINE=BLOCKED_DOCKER_MISSING' }
$drive = Get-PSDrive -Name C -ErrorAction SilentlyContinue
if ($null -eq $drive) { Write-Output 'P520_STORAGE_SPACE=UNVERIFIED' }
elseif ($drive.Free -ge 12GB) { Write-Output 'P520_STORAGE_SPACE_12GIB=PASS' }
else { Write-Output 'P520_STORAGE_SPACE_12GIB=BLOCKED' }
Write-Output 'P520_OFFSITE_OBJECT_RECEIVED=NOT_VERIFIED'
Write-Output 'P520_INDEPENDENT_DECRYPT_RESTORE=NOT_EXECUTED'
Write-Output 'P520_PRIVATE_SIGNING_KEY=NOT_ACCESSED'
Write-Output 'PRODUCTION_DB_MUTATION=NONE'
Write-Output 'PRODUCTION_RELEASE_APPROVAL=NOT_GRANTED'
