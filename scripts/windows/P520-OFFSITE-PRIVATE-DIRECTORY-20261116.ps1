# KMJ P520 offsite key+inbox dedicated Windows ACL provisioning.
# Owner-only, no network, no private keys, no old file overwrite, no backup read.
[CmdletBinding()]
param([switch]$Inspect,[switch]$Provision)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
function Block([string]$Reason) {
    Write-Output "KMJ_P520_PRIVATE_DIRECTORY=BLOCKED_$Reason"
    Write-Output "PRIVATE_KEY_CREATED=NO"
    Write-Output "PRODUCTION_APPROVAL=NOT_GRANTED"
    exit 2
}
if ([bool]$Inspect -eq [bool]$Provision) { Block 'EXACT_ONE_MODE' }
if ($env:OS -ne 'Windows_NT' -or $env:COMPUTERNAME -ne 'DESKTOP-5FVJMET') { Block 'WRONG_P520_HOST' }
$local = [Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)
if ([string]::IsNullOrWhiteSpace($local) -or -not [IO.Directory]::Exists($local)) { Block 'LOCAL_APPDATA' }
$root = Join-Path $local 'KMJ-Private-Offsite-Recovery'
$inbox = Join-Path $root 'inbox'
$mySid = [Security.Principal.WindowsIdentity]::GetCurrent().User
$allowed = @($mySid.Value,'S-1-5-18','S-1-5-32-544')
function Valid-Dir([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) { return $false }
    $item = Get-Item -LiteralPath $Path -Force
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { return $false }
    $acl = Get-Acl -LiteralPath $Path
    if (-not $acl.AreAccessRulesProtected) { return $false }
    if ($acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -ne $mySid.Value) { return $false }
    $rules = @($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    if ($rules.Count -lt 1 -or $rules.Count -gt 12) { return $false }
    $ownerFull = $false
    foreach ($rule in $rules) {
        $sid = $rule.IdentityReference.Value
        if ($allowed -notcontains $sid -or $rule.IsInherited -or
            $rule.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow -or
            ($rule.FileSystemRights -band [Security.AccessControl.FileSystemRights]::FullControl) -ne [Security.AccessControl.FileSystemRights]::FullControl) {
            return $false
        }
        if ($sid -eq $mySid.Value) { $ownerFull = $true }
    }
    return $ownerFull
}
function Private-Dir([string]$Path) {
    if (Test-Path -LiteralPath $Path) {
        if (-not (Valid-Dir $Path)) { Block 'EXISTING_DIRECTORY_NOT_PRIVATE' }
        return
    }
    $null = [IO.Directory]::CreateDirectory($Path)
    $acl = New-Object System.Security.AccessControl.DirectorySecurity
    $acl.SetOwner($mySid)
    $acl.SetAccessRuleProtection($true,$false)
    $flags = [Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [Security.AccessControl.InheritanceFlags]::ObjectInherit
    foreach ($sid in $allowed) {
        $who = [Security.Principal.SecurityIdentifier]::new($sid)
        $rule = [Security.AccessControl.FileSystemAccessRule]::new($who,[Security.AccessControl.FileSystemRights]::FullControl,$flags,[Security.AccessControl.PropagationFlags]::None,[Security.AccessControl.AccessControlType]::Allow)
        $acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $Path -AclObject $acl
    if (-not (Valid-Dir $Path)) { Block 'POSTCREATE_ACL_UNVERIFIED' }
}
try {
    if ($Provision) {
        Private-Dir $root
        Private-Dir $inbox
    }
    if (-not (Valid-Dir $root) -or -not (Valid-Dir $inbox)) { Block 'PRIVATE_DIRECTORY_NOT_READY' }
} catch {
    Block 'FILESYSTEM_OR_ACL_FAILURE'
}
Write-Output 'KMJ_P520_PRIVATE_DIRECTORY=PASS'
Write-Output 'ACL_PROTECTED_OWNER_SYSTEM_ADMINS=PASS'
Write-Output 'GOOGLE_VPS_REQUIRED=NO'
Write-Output 'P520_AGE_PRIVATE_KEY=NOT_GENERATED'
Write-Output 'P520_ENCRYPTED_BACKUP=NOT_RECEIVED'
Write-Output 'P520_INDEPENDENT_RESTORE=NOT_EXECUTED'
Write-Output 'PRODUCTION_APPROVAL=NOT_GRANTED'
