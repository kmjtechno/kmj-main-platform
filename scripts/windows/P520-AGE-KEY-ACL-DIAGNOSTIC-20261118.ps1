# KMJ TECHNO - owner P520 AGE private file ACL diagnosis, READ ONLY.
# No key read, secret/SID/path output, service action, private-key rewrite or ACL mutation.
[CmdletBinding()]
param([switch]$Inspect)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Mark([string]$k,[string]$v){ Write-Output ($k+'='+$v) }
function Fail([string]$code){
  Mark 'P520_AGE_KEY_ACL_DIAGNOSTIC' ('BLOCKED_'+$code)
  Mark 'P520_HOST_MUTATION' 'NONE'
  exit 2
}
if(-not $Inspect){Fail 'INSPECT_REQUIRED'}
if($env:OS -cne 'Windows_NT' -or $env:COMPUTERNAME -ine 'DESKTOP-5FVJMET'){Fail 'OWNER_P520_ONLY'}
try {
  $local=[Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)
  if([string]::IsNullOrWhiteSpace($local)){Fail 'LOCALAPPDATA_MISSING'}
  $private=Join-Path $local 'KMJ-Private-Offsite-Recovery'
  $file=Join-Path $private 'p520-offsite.agekey'
  $base=Get-Item -LiteralPath $private -Force -ErrorAction Stop
  if(-not $base.PSIsContainer -or ($base.Attributes -band [IO.FileAttributes]::ReparsePoint)){Fail 'PARENT_NOT_ORDINARY_DIRECTORY'}
  $parentAcl=Get-Acl -LiteralPath $private -ErrorAction Stop
  $me=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
  $parentOwner=$parentAcl.GetOwner([Security.Principal.SecurityIdentifier]).Value
  if(-not $parentAcl.AreAccessRulesProtected -or $parentOwner -cne $me){Fail 'PARENT_OWNER_OR_ACL_UNTRUSTED'}
  Mark 'P520_KEY_PARENT_OWNER_AND_PROTECTED_ACL' 'PASS'
  $item=Get-Item -LiteralPath $file -Force -ErrorAction Stop
  if($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)){Fail 'AGE_KEY_NONREGULAR'}
  if($item.Length -lt 40 -or $item.Length -gt 8192){Fail 'AGE_KEY_SIZE_OUT_OF_BOUNDS'}
  Mark 'P520_KEY_FILE_REGULAR_AND_BOUNDED' 'PASS'
  $acl=Get-Acl -LiteralPath $file -ErrorAction Stop
  $fileOwner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value
  $allowed=@($me,'S-1-5-18','S-1-5-32-544')
  $rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
  $foreign=0;$denied=0;$insufficient=0;$inherited=0;$ownerRead=$false;$ownerFull=$false;$ownerRule=$false
  foreach($ace in $rules){
    $sid=[string]$ace.IdentityReference.Value
    if($allowed -notcontains $sid){$foreign++}
    if($ace.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow){$denied++}
    if([bool]$ace.IsInherited){$inherited++}
    $full=(($ace.FileSystemRights -band [Security.AccessControl.FileSystemRights]::FullControl) -eq [Security.AccessControl.FileSystemRights]::FullControl)
    if(-not $full){$insufficient++}
    if($sid -ceq $me -and $ace.AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow){
      $ownerRule=$true
      if(($ace.FileSystemRights -band [Security.AccessControl.FileSystemRights]::ReadData) -ne 0){$ownerRead=$true}
      if($full){$ownerFull=$true}
    }
  }
  Mark 'P520_AGE_FILE_OWNER_IS_CURRENT_USER' $(if($fileOwner -ceq $me){'PASS'}else{'FAIL'})
  Mark 'P520_AGE_FILE_ACL_INHERITANCE' $(if($acl.AreAccessRulesProtected){'PROTECTED'}else{'INHERITED'})
  Mark 'P520_AGE_FILE_ACL_RULE_COUNT' ([string]$rules.Count)
  Mark 'P520_AGE_FILE_FOREIGN_PRINCIPAL' $(if($foreign -eq 0){'NONE'}else{'PRESENT_BLOCKED'})
  Mark 'P520_AGE_FILE_DENY_ACE' $(if($denied -eq 0){'NONE'}else{'PRESENT_BLOCKED'})
  Mark 'P520_AGE_FILE_INHERITED_ACE' $(if($inherited -eq 0){'NONE'}else{'PRESENT'})
  Mark 'P520_AGE_FILE_NONFULL_ACE' $(if($insufficient -eq 0){'NONE'}else{'PRESENT'})
  Mark 'P520_AGE_FILE_OWNER_HAS_READ' $(if($ownerRead){'YES'}else{'NO'})
  Mark 'P520_AGE_FILE_OWNER_HAS_FULL' $(if($ownerFull){'YES'}else{'NO'})
  $ok=($fileOwner -ceq $me -and $rules.Count -ge 1 -and $rules.Count -le 12 -and $foreign -eq 0 -and $denied -eq 0 -and $insufficient -eq 0 -and $ownerRule -and $ownerFull)
  Mark 'P520_EXISTING_HELPER_ACL_CONTRACT' $(if($ok){'PASS'}else{'FAIL'})
  Mark 'P520_KEY_CONTENT_EXPOSED' 'NO'
  Mark 'P520_HOST_MUTATION' 'NONE'
  Mark 'P520_AGE_KEY_ACL_DIAGNOSTIC' 'COMPLETE'
} catch {
  Fail 'ACL_OR_METADATA_UNAVAILABLE'
}
