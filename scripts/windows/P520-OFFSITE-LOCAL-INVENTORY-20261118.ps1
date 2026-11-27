# KMJ P520 independent offsite readiness: bounded read-only inventory.
# No secrets or paths printed; no network/transfer/decrypt, no backup or Docker changes.
# V1 4C9 artifact is NOT valid recovery proof for newer Licensing Hub releases.
[CmdletBinding()]
param([switch]$Inspect)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Mark([string]$Name,[string]$State) { Write-Output ($Name+'='+$State) }
function State([string]$File,[bool]$Directory=$false) {
  if(-not (Test-Path -LiteralPath $File)) { return 'MISSING' }
  try {
    $entry=Get-Item -LiteralPath $File -Force -ErrorAction Stop
    if([bool]$entry.PSIsContainer -ne $Directory -or
       ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
      return 'UNSAFE'
    }
    return 'PRESENT_UNATTESTED'
  } catch { return 'UNVERIFIED' }
}
function PrivateDir([string]$Folder,[string]$OwnerSid) {
  if((State $Folder $true) -ne 'PRESENT_UNATTESTED') { return 'NOT_READY' }
  try {
    $acl=Get-Acl -LiteralPath $Folder -ErrorAction Stop
    if(-not $acl.AreAccessRulesProtected) { return 'UNSAFE_ACL' }
    if($acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -cne $OwnerSid) {
      return 'UNTRUSTED_OWNER'
    }
    $allowed=@($OwnerSid,'S-1-5-18','S-1-5-32-544')
    $rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    if($rules.Count -eq 0 -or $rules.Count -gt 12) { return 'UNSAFE_ACL' }
    $ownerFull=$false
    foreach($ace in $rules) {
      $sid=$ace.IdentityReference.Value
      if($allowed -notcontains $sid -or $ace.IsInherited -or
         $ace.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow -or
         ($ace.FileSystemRights -band [Security.AccessControl.FileSystemRights]::FullControl) -ne
         [Security.AccessControl.FileSystemRights]::FullControl) {
         return 'UNSAFE_ACL'
      }
      if($sid -ceq $OwnerSid){$ownerFull=$true}
    }
    if(-not $ownerFull){return 'UNSAFE_ACL'}
    return 'PASS'
  } catch { return 'UNVERIFIED' }
}
try {
  if(-not $Inspect){Mark 'P520_READONLY_INVENTORY' 'BLOCKED_EXPLICIT_INSPECT_REQUIRED';exit 2}
  if($env:OS -cne 'Windows_NT' -or $env:COMPUTERNAME -ine 'DESKTOP-5FVJMET'){
    Mark 'P520_READONLY_INVENTORY' 'BLOCKED_WRONG_OWNER_HOST';exit 2
  }
  $local=[Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)
  if([string]::IsNullOrWhiteSpace($local) -or (State $local $true) -ne 'PRESENT_UNATTESTED'){
    Mark 'P520_READONLY_INVENTORY' 'BLOCKED_LOCALAPPDATA_UNTRUSTED';exit 2
  }
  $ownerSid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
  $root=Join-Path $local 'KMJ-Private-Offsite-Recovery'
  $inbox=Join-Path $root 'inbox'
  $rootAcl=PrivateDir $root $ownerSid
  $inboxAcl=PrivateDir $inbox $ownerSid
  Mark 'P520_PRIVATE_ROOT_ACL' $rootAcl
  Mark 'P520_PRIVATE_INBOX_ACL' $inboxAcl
  if($rootAcl -cne 'PASS' -or $inboxAcl -cne 'PASS'){
    Mark 'P520_INBOX_FILES' 'NOT_INSPECTED_UNTRUSTED_DIRECTORY'
    Mark 'P520_READONLY_INVENTORY' 'BLOCKED_PRIVATE_DIRECTORY'
    Mark 'P520_HOST_MUTATION' 'NONE'
    Mark 'PRODUCTION_RELEASE_APPROVAL' 'NOT_GRANTED'
    exit 2
  }
  # Fixed paths; only metadata. Never read or print an AGE secret, signer or encrypted data.
  $files=[ordered]@{
    P520_AGE_PRIVATE_KEY=(Join-Path $root 'p520-offsite.agekey')
    P520_AGE_PUBLIC_RECIPIENT=(Join-Path $root 'p520-age-recipient.txt')
    P520_ED25519_PRIVATE_SIGNER=(Join-Path $root 'p520-receipt-signing-ed25519.pem')
    P520_ED25519_PUBLIC_SIGNER=(Join-Path $root 'p520-receipt-ed25519-public.pem')
    P520_RESTORE_IMAGE_PIN=(Join-Path $root 'restore-image.sha256')
    P520_V1_4C9_CIPHER=(Join-Path $inbox 'offsite-p520-4c9d59103b99.tar.gz.age')
    P520_V1_4C9_CIPHER_PARTIAL=(Join-Path $inbox 'offsite-p520-4c9d59103b99.tar.gz.age.partial')
  }
  foreach($item in $files.GetEnumerator()){
    Mark ([string]$item.Key) (State ([string]$item.Value))
  }
  $keygen=Get-Command age-keygen.exe -ErrorAction SilentlyContinue
  Mark 'P520_AGE_KEYGEN' $(if($null -eq $keygen){'MISSING'}else{'PRESENT'})
  # Owner-pin validation only, not an image pull or a build. No secret is present in this file.
  $policy=$files['P520_RESTORE_IMAGE_PIN']
  $pin='';$image='NOT_VERIFIED'
  if((State $policy) -eq 'PRESENT_UNATTESTED'){
    try{
      $info=Get-Item -LiteralPath $policy -Force -ErrorAction Stop
      if($info.Length -lt 64 -or $info.Length -gt 66){$image='INVALID_PIN_LENGTH'}
      else {
        $value=[IO.File]::ReadAllText($policy).Trim()
        if($value -cnotmatch '^[0-9a-f]{64}$'){$image='INVALID_PIN_FORMAT'}
        else {$pin=$value;$image='PIN_FORMAT_PASS'}
      }
    }catch{$image='PIN_UNREADABLE'}
  }else{$image='OWNER_PIN_MISSING_OR_UNTRUSTED'}
  Mark 'P520_IMAGE_POLICY' $image
  if($image -eq 'PIN_FORMAT_PASS'){
    $docker=Get-Command docker.exe -ErrorAction SilentlyContinue
    if($null -eq $docker){Mark 'P520_PINNED_DOCKER_IMAGE' 'DOCKER_MISSING'}
    else {
      try{
        $endpoint=[string]((& docker.exe context inspect --format '{{(index .Endpoints "docker").Host}}' 2>$null) | Select-Object -First 1)
        if($LASTEXITCODE -ne 0 -or $endpoint -cnotin @(
          'npipe:////./pipe/dockerDesktopLinuxEngine',
          'npipe:////./pipe/docker_engine')){
          Mark 'P520_PINNED_DOCKER_IMAGE' 'BLOCKED_NONLOCAL_DOCKER_ENDPOINT'
        }else{
          $id=[string]((& docker.exe image inspect --format '{{.Id}}' ('sha256:'+$pin) 2>$null) | Select-Object -First 1)
          if($LASTEXITCODE -eq 0 -and $id.Trim() -ceq ('sha256:'+$pin)){
            Mark 'P520_PINNED_DOCKER_IMAGE' 'PASS_LOCAL_IMMUTABLE'
          }else {Mark 'P520_PINNED_DOCKER_IMAGE' 'MISSING_OR_ID_MISMATCH'}
        }
      }catch{Mark 'P520_PINNED_DOCKER_IMAGE' 'UNVERIFIED'}
    }
  }else{Mark 'P520_PINNED_DOCKER_IMAGE' 'NOT_CHECKED_NO_VALID_POLICY'}
  Mark 'P520_LICENSING_HUB_CANDIDATE_CIPHER' 'NOT_CONFIGURED_IN_V1'
  Mark 'P520_FULL_CIPHER_SHA_READBACK' 'NOT_EXECUTED'
  Mark 'P520_INDEPENDENT_PG_STORAGE_RESTORE' 'NOT_EXECUTED'
  Mark 'P520_OWNER_SIGNED_RESTORE_RECEIPT' 'NOT_VERIFIED'
  Mark 'P520_HOST_MUTATION' 'NONE'
  Mark 'PRODUCTION_RELEASE_APPROVAL' 'NOT_GRANTED'
  Mark 'P520_READONLY_INVENTORY' 'COMPLETE'
}catch{
  Mark 'P520_READONLY_INVENTORY' 'BLOCKED_READONLY_INSPECTION_ERROR'
  Mark 'P520_HOST_MUTATION' 'NONE'
  Mark 'PRODUCTION_RELEASE_APPROVAL' 'NOT_GRANTED'
  exit 2
}
