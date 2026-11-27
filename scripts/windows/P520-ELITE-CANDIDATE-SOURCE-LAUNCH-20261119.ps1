# KMJ P520 exact-source, owner-only read-only candidate witness launcher.
# Transfers only a SHA-pinned public script. Never copies private keys,
# backup bytes or production data. Never invokes --prepare/--apply/--execute.
[CmdletBinding()]
param([switch]$Inspect)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

function Fail([string]$reason) {
  Write-Output ('KMJ_P520_CANDIDATE_SOURCE_LAUNCH=BLOCKED_'+$reason)
  Write-Output 'P520_ENCRYPTED_TRANSFER_OR_RESTORE=NOT_EXECUTED'
  Write-Output 'PRODUCTION_APPROVAL=NOT_GRANTED'
  exit 2
}
if(-not $Inspect) {Fail 'EXPLICIT_INSPECT_REQUIRED'}
if($env:OS -cne 'Windows_NT' -or $env:COMPUTERNAME -ine 'DESKTOP-5FVJMET'){
  Fail 'WRONG_P520_DEVICE'
}

$local=Join-Path $PSScriptRoot 'P520-ELITE-CURRENT-CANDIDATE-SOURCE-DOCTOR-20261118.sh'
$sha='d794608cc381c6c9190164a91bb3292a3042a6d8d4d087a4589f35acf8255ef7'
$destination='root@150.242.200.81'
$remote='/root/kmj-p520-candidate-source-doctor-d794608c.sh'
try {
  $f=Get-Item -LiteralPath $local -Force -ErrorAction Stop
  if($f.PSIsContainer -or ($f.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
     $f.Length -lt 4000 -or $f.Length -gt 12000) {
    Fail 'PINNED_SOURCE_METADATA'
  }
  $actual=(Get-FileHash -LiteralPath $local -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
  if($actual -cne $sha){ Fail 'PINNED_SOURCE_HASH_MISMATCH' }
  $null=Get-Command scp.exe -ErrorAction Stop
  $null=Get-Command ssh.exe -ErrorAction Stop

  Write-Output 'KMJ_P520_CANDIDATE_SOURCE_LOCAL_SHA256=PASS'
  # OpenSSH fails closed if the host key differs from the known pinned host.
  # Owner may be prompted to authenticate with the server; no secret is read here.
  $target=$destination+':'+$remote
  & scp.exe -o StrictHostKeyChecking=yes $local $target
  if($LASTEXITCODE -ne 0){Fail 'TRUSTED_SCP_TRANSFER_FAILED'}
  $cmd="printf '%s  %s\n' '$sha' '$remote' | /usr/bin/sha256sum -c - && /bin/bash '$remote' --inspect"
  & ssh.exe -o StrictHostKeyChecking=yes $destination $cmd
  if($LASTEXITCODE -ne 0){Fail 'ELITE_READONLY_DOCTOR_FAILED'}
  Write-Output 'KMJ_P520_CANDIDATE_SOURCE_LAUNCH=REMOTE_READONLY_COMPLETE'
  Write-Output 'P520_ENCRYPTED_TRANSFER_OR_RESTORE=NOT_EXECUTED'
  Write-Output 'PRODUCTION_APPROVAL=NOT_GRANTED'
} catch {
  Fail 'SOURCE_OR_TRANSPORT_PRECONDITION_UNVERIFIED'
}
