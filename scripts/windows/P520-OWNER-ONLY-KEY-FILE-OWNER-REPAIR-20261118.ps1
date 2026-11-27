# KMJ TECHNO P520 protected recovery - fixed key owner repair (not ACL grant).
# Owner-only guarded operation: never reads/writes key material or alters access ACEs.
# -Inspect previews; -Repair changes OWNER ONLY of safe existing files if currently
# owned by SYSTEM/Administrators. It NEVER creates/replaces or rotates keys.
[CmdletBinding()]
param([switch]$Inspect,[switch]$Repair)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Mark([string]$k,[string]$v) { Write-Output ($k+'='+$v) }
function Deny([string]$code) { throw ('KMJ_'+$code) }
function Snapshot([System.Security.AccessControl.FileSystemSecurity]$acl) {
  $rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
  $parts=@(foreach($rule in $rules) {
    $sid=$rule.IdentityReference.Value
    $rights=[int64]$rule.FileSystemRights
    $type=$rule.AccessControlType.ToString()
    $inherited=[bool]$rule.IsInherited
    $flags=[int]$rule.InheritanceFlags
    $prop=[int]$rule.PropagationFlags
    "$sid|$rights|$type|$inherited|$flags|$prop"
  })
  return (($parts | Sort-Object -CaseSensitive) -join ';')
}
function VerifyFile([string]$file,[int]$max,[string]$userSid) {
  $item=Get-Item -LiteralPath $file -Force -ErrorAction Stop
  if($item.PSIsContainer -or
     ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
     $item.Length -lt 32 -or $item.Length -gt $max) {
    Deny 'FILE_TYPE_OR_SIZE_UNSAFE'
  }
  $acl=Get-Acl -LiteralPath $file -ErrorAction Stop
  $owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value
  $allowed=@($userSid,'S-1-5-18','S-1-5-32-544')
  if($owner -cnotin $allowed){ Deny 'UNTRUSTED_FILE_OWNER' }
  $rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
  if($rules.Count -lt 1 -or $rules.Count -gt 12){ Deny 'FILE_ACL_RULE_COUNT_UNSAFE' }
  $userFull=$false
  foreach($ace in $rules) {
    $sid=$ace.IdentityReference.Value
    $full=(($ace.FileSystemRights -band [Security.AccessControl.FileSystemRights]::FullControl) -eq [Security.AccessControl.FileSystemRights]::FullControl)
    if($allowed -notcontains $sid -or
       $ace.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow -or
       -not $full) { Deny 'FILE_ACL_UNSAFE' }
    if($sid -ceq $userSid){$userFull=$true}
  }
  if(-not $userFull) { Deny 'CURRENT_OWNER_ACCOUNT_LACKS_FULL_ACCESS' }
  return [PSCustomObject]@{Acl=$acl;Owner=$owner;Snapshot=(Snapshot $acl)}
}
try {
  if([bool]$Inspect -eq [bool]$Repair){ Deny 'EXACT_ONE_MODE_REQUIRED' }
  if($env:OS -cne 'Windows_NT' -or $env:COMPUTERNAME -ine 'DESKTOP-5FVJMET'){Deny 'WRONG_P520_OWNER_DEVICE'}
  $local=[Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)
  if([string]::IsNullOrWhiteSpace($local)){Deny 'LOCALAPPDATA_MISSING'}
  $root=Join-Path $local 'KMJ-Private-Offsite-Recovery'
  $item=Get-Item -LiteralPath $root -Force -ErrorAction Stop
  if(-not $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){Deny 'UNTRUSTED_PRIVATE_ROOT'}
  $mySid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
  $ownerName=[Security.Principal.WindowsIdentity]::GetCurrent().Name
  $rootAcl=Get-Acl -LiteralPath $root -ErrorAction Stop
  if(-not $rootAcl.AreAccessRulesProtected -or
     $rootAcl.GetOwner([Security.Principal.SecurityIdentifier]).Value -cne $mySid){Deny 'UNTRUSTED_PARENT_OWNER_OR_ACL'}
  $allowed=@($mySid,'S-1-5-18','S-1-5-32-544')
  $parentRules=@($rootAcl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
  if($parentRules.Count -lt 1 -or $parentRules.Count -gt 12){Deny 'PARENT_ACL_RULE_COUNT'}
  $parentOwnerFull=$false
  foreach($r in $parentRules){
    $sid=$r.IdentityReference.Value
    $full=(($r.FileSystemRights -band [Security.AccessControl.FileSystemRights]::FullControl) -eq [Security.AccessControl.FileSystemRights]::FullControl)
    if($allowed -notcontains $sid -or $r.IsInherited -or
       $r.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow -or
       -not $full){Deny 'UNTRUSTED_PARENT_ACL'}
    if($sid -ceq $mySid){$parentOwnerFull=$true}
  }
  if(-not $parentOwnerFull){Deny 'PARENT_OWNER_NOT_FULL_CONTROL'}
  Mark 'P520_PRIVATE_PARENT_ACL' 'PASS'
  $files=@(
    [PSCustomObject]@{Label='AGE_PRIVATE';Name='p520-offsite.agekey';Max=8192},
    [PSCustomObject]@{Label='AGE_PUBLIC';Name='p520-age-recipient.txt';Max=256},
    [PSCustomObject]@{Label='ED25519_PRIVATE';Name='p520-receipt-signing-ed25519.pem';Max=8192},
    [PSCustomObject]@{Label='ED25519_PUBLIC';Name='p520-receipt-ed25519-public.pem';Max=4096}
  )
  $preflight=@(foreach($spec in $files) {
    $file=Join-Path $root $spec.Name
    $state=VerifyFile $file $spec.Max $mySid
    [PSCustomObject]@{ Label=$spec.Label; Path=$file; Max=$spec.Max; Before=$state }
  })
  Mark 'P520_FILE_SET_PRECHECK' 'PASS'
  $needs=@($preflight | Where-Object { $_.Before.Owner -cne $mySid })
  Mark 'P520_FILE_OWNER_MISMATCH_COUNT' ([string]$needs.Count)
  if($Inspect) {
    Mark 'P520_OWNER_REPAIR' 'READ_ONLY_REVIEW'
    Mark 'P520_HOST_MUTATION' 'NONE'
    exit 0
  }
  $aclExe=Join-Path $env:SystemRoot 'System32\icacls.exe'
  if(-not (Test-Path -LiteralPath $aclExe -PathType Leaf)){Deny 'ICACLS_NOT_FOUND'}
  $changed=0
  foreach($entry in $needs) {
    # /setowner affects file owner only. NEVER /grant, /reset, /inheritance, /T.
    $null=& $aclExe $entry.Path '/setowner' $ownerName 2>$null
    if($LASTEXITCODE -ne 0){Deny 'OWNER_ONLY_OPERATION_FAILED'}
    $after=VerifyFile $entry.Path $entry.Max $mySid
    if($after.Owner -cne $mySid -or $after.Snapshot -cne $entry.Before.Snapshot -or
       $after.Acl.AreAccessRulesProtected -ne $entry.Before.Acl.AreAccessRulesProtected){
      Deny 'POST_REPAIR_DACL_OR_OWNER_MISMATCH'
    }
    $changed++
  }
  # Also verify originally correct-owner files remain unchanged.
  foreach($entry in $preflight) {
    $now=VerifyFile $entry.Path $entry.Max $mySid
    if($now.Owner -cne $mySid -or $now.Snapshot -cne $entry.Before.Snapshot -or
       $now.Acl.AreAccessRulesProtected -ne $entry.Before.Acl.AreAccessRulesProtected) {
      Deny 'FINAL_VERIFY_FAILED'
    }
  }
  Mark 'P520_FIXED_KEY_FILES' 'FOUR_VERIFIED'
  Mark 'P520_FILE_OWNER_ONLY_REPAIRED' ([string]$changed)
  Mark 'P520_KEY_CONTENT_READ_OR_REPLACED' 'NO'
  Mark 'P520_DACL_GRANTS_OR_INHERITANCE_CHANGED' 'NO'
  Mark 'P520_CODEBRIDGE_OR_PRODUCTION' 'UNTOUCHED'
  Mark 'P520_OWNER_REPAIR' 'PASS'
  Mark 'PRODUCTION_APPROVAL' 'NOT_GRANTED'
} catch {
  $reason=[string]$_.Exception.Message
  if($reason -notmatch '^KMJ_[A-Z0-9_]{4,90}$'){$reason='KMJ_REVIEW_REQUIRED'}
  Mark 'P520_OWNER_REPAIR' ('BLOCKED_'+$reason.Substring(4))
  Mark 'P520_NEVER_OVERWRITE_KEYS' 'YES'
  Mark 'PRODUCTION_APPROVAL' 'NOT_GRANTED'
  exit 2
}
