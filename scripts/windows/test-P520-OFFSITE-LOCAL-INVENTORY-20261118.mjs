import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
const filename='scripts/windows/P520-OFFSITE-LOCAL-INVENTORY-20261118.ps1';
const src=readFileSync(filename,'utf8');

test('P520 v1 inventory is opt-in read only, never treats legacy 4C9 as KSLP recovery evidence',()=>{
 for(const marker of ['[CmdletBinding()]','param([switch]$Inspect)','Set-StrictMode -Version Latest',
    'P520_V1_4C9_CIPHER','P520_LICENSING_HUB_CANDIDATE_CIPHER',
    'NOT_CONFIGURED_IN_V1','P520_FULL_CIPHER_SHA_READBACK',
    'P520_INDEPENDENT_PG_STORAGE_RESTORE','NOT_EXECUTED',
    'P520_HOST_MUTATION','PRODUCTION_RELEASE_APPROVAL','NOT_GRANTED']){
    assert.ok(src.includes(marker),marker);
 }
 assert.doesNotMatch(src,/\$args\b|(?<!\w)(?:Start|Restart|Enable|Stop|Unregister|Register)-ScheduledTask|(?:Restart|Start|Stop)-Service|Set-Acl|Set-Content|Remove-Item|New-Item|Invoke-Expression|Invoke-WebRequest|docker.exe\s+(?:run|build|pull|volume|exec)/i);
 assert.doesNotMatch(src,/Write-Output\s+\$pin|Mark\s+['"]P520_AGE_PRIVATE_KEY['"]\s+\$root/i);
});
test('only the known v1 object and dedicated private directory are inspected',()=>{
 assert.match(src,/KMJ-Private-Offsite-Recovery/);
 assert.match(src,/offsite-p520-4c9d59103b99\.tar\.gz\.age/);
 assert.match(src,/P520_PRIVATE_ROOT_ACL/);
 assert.match(src,/P520_PRIVATE_INBOX_ACL/);
 assert.match(src,/P520_PINNED_DOCKER_IMAGE/);
 assert.match(src,/BLOCKED_NONLOCAL_DOCKER_ENDPOINT/);
 assert.doesNotMatch(src,/Get-ChildItem|Invoke-RestMethod|curl|wget/i);
});
test('native PowerShell parser and opt-in host gate', {skip:process.platform!=='win32'},()=>{
 const parser=[
 "$ErrorActionPreference='Stop';",
 "$tok=$null;$err=$null;",
 "[System.Management.Automation.Language.Parser]::ParseFile('"+filename+"',[ref]$tok,[ref]$err)|Out-Null;",
 "if($err.Count -gt 0){throw ('PS_PARSER_ERRORS='+$err.Count)}"
 ].join('');
 const p=spawnSync('powershell.exe',['-NoProfile','-NonInteractive','-Command',parser],{encoding:'utf8',timeout:15000});
 assert.equal(p.status,0,p.stderr+p.stdout);
 const missing=spawnSync('powershell.exe',['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',filename],{encoding:'utf8',timeout:15000});
 assert.equal(missing.status,2,missing.stderr);
 assert.match(missing.stdout,/BLOCKED_EXPLICIT_INSPECT_REQUIRED/);
 const host=spawnSync('powershell.exe',['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',filename,'-Inspect'],{encoding:'utf8',timeout:15000});
 assert.equal(host.status,2,host.stderr);
 assert.match(host.stdout,/BLOCKED_WRONG_OWNER_HOST/);
 assert.doesNotMatch(host.stdout,/P520_PINNED_DOCKER_IMAGE=PASS_LOCAL_IMMUTABLE/);
});
