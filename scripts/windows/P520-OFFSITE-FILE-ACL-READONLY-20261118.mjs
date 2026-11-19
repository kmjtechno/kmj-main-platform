// Read-only SID-based Windows ACL check for a key/public file beneath a
// previously validated owner-private directory. Child NTFS inheritance is
// allowed only from trusted owner/SYSTEM/Administrators; foreign ACEs deny.
import { spawnSync } from 'node:child_process';

const SID=/^S-1-[0-9]+(?:-[0-9]+)+$/;
const SYSTEM='S-1-5-18', ADMINS='S-1-5-32-544';

export function trustedPrivateChildFileAcl(report) {
  if(!report || typeof report!=='object' || Array.isArray(report) ||
     typeof report.OwnerSid!=='string' || !SID.test(report.OwnerSid) ||
     report.UserSid!==report.OwnerSid ||
     !Array.isArray(report.Rules) || report.Rules.length<1 || report.Rules.length>12)
     return false;
  const allowed=new Set([report.UserSid,SYSTEM,ADMINS]);
  let ownerFull=false;
  for(const r of report.Rules) {
    if(!r || typeof r!=='object' || !allowed.has(r.Sid) ||
       r.Type!=='Allow' || typeof r.Inherited!=='boolean' ||
       r.FullControl!==true) return false;
    if(r.Sid===report.UserSid) ownerFull=true;
  }
  return ownerFull;
}

const SCRIPT=[
  "$ErrorActionPreference='Stop'",
  "$p=$env:KMJ_P520_ACL_PATH",
  "if([string]::IsNullOrWhiteSpace($p)){throw 'NO_PATH'}",
  "$file=Get-Item -LiteralPath $p -Force -ErrorAction Stop",
  "if($file.PSIsContainer -or ($file.Attributes -band [IO.FileAttributes]::ReparsePoint)){throw 'NOT_ORDINARY_FILE'}",
  "$security=Get-Acl -LiteralPath $p -ErrorAction Stop",
  "$me=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value",
  "$owner=$security.GetOwner([Security.Principal.SecurityIdentifier]).Value",
  "$rules=@($security.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | ForEach-Object {",
  " [PSCustomObject]@{",
  "  Sid=$_.IdentityReference.Value",
  "  Type=$_.AccessControlType.ToString()",
  "  Inherited=[bool]$_.IsInherited",
  "  FullControl=(($_.FileSystemRights -band [Security.AccessControl.FileSystemRights]::FullControl) -eq [Security.AccessControl.FileSystemRights]::FullControl)",
  " }",
  "})",
  "[PSCustomObject]@{OwnerSid=$owner; UserSid=$me; Rules=$rules} | ConvertTo-Json -Compress -Depth 5"
].join('\n');

export function verifyWindowsPrivateChildFileAcl(file) {
  if(process.platform!=='win32'||typeof file!=='string'||!file||file.length>1024||
     /[\r\n\0]/.test(file)) return false;
  const command=Buffer.from(SCRIPT,'utf16le').toString('base64');
  const run=spawnSync('powershell.exe',[
    '-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-EncodedCommand',command
  ],{encoding:'utf8',timeout:15000,maxBuffer:16384,windowsHide:true,
    env:{...process.env,KMJ_P520_ACL_PATH:file}});
  if(run.status!==0||!run.stdout||run.stdout.length>12000)return false;
  try{return trustedPrivateChildFileAcl(JSON.parse(run.stdout.trim()));}
  catch{return false;}
}
