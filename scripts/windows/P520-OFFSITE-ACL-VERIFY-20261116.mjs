#!/usr/bin/env node
// Exact Windows SID ACL checker for P520 private keys and encrypted backup inbox.
// Queries Get-Acl read-only; disallows all foreign/inherited ACL principals.
import { spawnSync } from 'node:child_process';

const SID=/^S-1-[0-9]+(?:-[0-9]+)+$/;
const SYSTEM='S-1-5-18', ADMINS='S-1-5-32-544';
export function trustedAclReport(report) {
  if (!report || typeof report!=='object' || Array.isArray(report) ||
      report.Protected!==true || !SID.test(report.OwnerSid??'') ||
      report.UserSid!==report.OwnerSid || !Array.isArray(report.Rules) ||
      report.Rules.length<1 || report.Rules.length>12) return false;
  const allowed=new Set([report.UserSid,SYSTEM,ADMINS]);
  let ownerFull=false;
  for(const r of report.Rules){
    if(!r || typeof r!=='object' || !allowed.has(r.Sid) ||
       r.Type!=='Allow' || r.Inherited!==false || r.FullControl!==true) return false;
    if(r.Sid===report.UserSid) ownerFull=true;
  }
  return ownerFull;
}
const SCRIPT=[
  "$ErrorActionPreference='Stop'",
  "$p=$env:KMJ_P520_ACL_PATH",
  "if ([string]::IsNullOrWhiteSpace($p)) { throw 'NO_PATH' }",
  "$security=Get-Acl -LiteralPath $p -ErrorAction Stop",
  "$mySid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value",
  "$ownerSid=$security.GetOwner([Security.Principal.SecurityIdentifier]).Value",
  "$all=@($security.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | ForEach-Object {",
  "    [PSCustomObject]@{",
  "        Sid=$_.IdentityReference.Value",
  "        Type=$_.AccessControlType.ToString()",
  "        Inherited=[bool]$_.IsInherited",
  "        FullControl=(($_.FileSystemRights -band [Security.AccessControl.FileSystemRights]::FullControl) -eq [Security.AccessControl.FileSystemRights]::FullControl)",
  "    }",
  "})",
  "[PSCustomObject]@{",
  "    Protected=[bool]$security.AreAccessRulesProtected",
  "    OwnerSid=$ownerSid",
  "    UserSid=$mySid",
  "    Rules=$all",
  "} | ConvertTo-Json -Compress -Depth 5"
].join('\n');
export function verifyWindowsPrivateAcl(path){
  if(process.platform!=='win32'||typeof path!=='string'||!path||path.length>1024)return false;
  const command=Buffer.from(SCRIPT,'utf16le').toString('base64');
  const p=spawnSync('powershell.exe',
    ['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-EncodedCommand',command],
    {encoding:'utf8',timeout:15000,maxBuffer:16384,
     env:{...process.env,KMJ_P520_ACL_PATH:path},windowsHide:true});
  if(p.status!==0||!p.stdout||p.stdout.length>10000)return false;
  try{return trustedAclReport(JSON.parse(p.stdout.trim()));}
  catch{return false;}
}
