import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
const file='scripts/windows/P520-AGE-KEY-ACL-DIAGNOSTIC-20261118.ps1';
const source=readFileSync(file,'utf8');

test('AGE ACL doctor has mandatory inspect and owner host and emits only categories',()=>{
 for(const marker of [
   '[CmdletBinding()]','param([switch]$Inspect)','Set-StrictMode -Version Latest',
   'DESKTOP-5FVJMET','BLOCKED_','P520_AGE_FILE_OWNER_IS_CURRENT_USER',
   'P520_AGE_FILE_FOREIGN_PRINCIPAL','P520_AGE_FILE_NONFULL_ACE',
   'P520_EXISTING_HELPER_ACL_CONTRACT','P520_KEY_CONTENT_EXPOSED','P520_HOST_MUTATION'
 ])assert.ok(source.includes(marker),marker);
 assert.doesNotMatch(source, /Get-Content|ReadAllBytes|ReadAllText|WriteAllText|Set-Acl|icacls.exe|New-Item|Set-Content|Remove-Item|Copy-Item|Move-Item|Start-Process|Start-Service|Enable-ScheduledTask|docker.exe|age-keygen.exe/i);
 assert.doesNotMatch(source,/Mark\s+['"]P520_(?:SID|PATH|SECRET|PRIVATE_KEY_BYTES)/);
});
test('PowerShell syntax and non-owner host check on Windows CI (no private files)',{skip:process.platform!=='win32'},()=>{
 const parser="$t=$null;$e=$null;[System.Management.Automation.Language.Parser]::ParseFile('"+file+"',[ref]$t,[ref]$e)|Out-Null;if($e.Count){throw 'PS_PARSE_FAILED'}";
 const checked=spawnSync('powershell.exe',['-NoProfile','-NonInteractive','-Command',parser],{encoding:'utf8',timeout:12000});
 assert.equal(checked.status,0,checked.stdout+checked.stderr);
 for(const args of [[],['-Inspect']]) {
   const r=spawnSync('powershell.exe',['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',file,...args],{encoding:'utf8',timeout:12000});
   assert.equal(r.status,2,r.stdout+r.stderr);
   assert.match(r.stdout,/P520_AGE_KEY_ACL_DIAGNOSTIC=BLOCKED_(?:INSPECT_REQUIRED|OWNER_P520_ONLY)/);
   assert.match(r.stdout,/P520_HOST_MUTATION=NONE/);
 }
});
