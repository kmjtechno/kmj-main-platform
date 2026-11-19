import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';

const file='scripts/windows/P520-ELITE-CANDIDATE-SOURCE-LAUNCH-20261119.ps1';
const source=readFileSync(file,'utf8');
const doctor=readFileSync('scripts/operations/kmj-p520-current-candidate-source-doctor-20261118.sh');
const pinned='d794608cc381c6c9190164a91bb3292a3042a6d8d4d087a4589f35acf8255ef7';

test('one-click launcher has exact source SHA and old source is byte-identical',()=>{
 assert.equal(createHash('sha256').update(doctor).digest('hex'),pinned);
 assert.ok(source.includes(pinned));
 for(const marker of [
   '[CmdletBinding()]','param([switch]$Inspect)','Set-StrictMode -Version Latest',
   'DESKTOP-5FVJMET','root@150.242.200.81',
   'P520-ELITE-CURRENT-CANDIDATE-SOURCE-DOCTOR-20261118.sh',
   'Get-FileHash','StrictHostKeyChecking=yes',
   "sha256sum -c - && /bin/bash '$remote' --inspect",
   'EXPLICIT_INSPECT_REQUIRED','WRONG_P520_DEVICE',
   'P520_ENCRYPTED_TRANSFER_OR_RESTORE=NOT_EXECUTED',
   'PRODUCTION_APPROVAL=NOT_GRANTED'
 ]) assert.ok(source.includes(marker),marker);
 assert.doesNotMatch(source,/StrictHostKeyChecking=no|UserKnownHostsFile=\/dev\/null|sshpass|Invoke-Expression|age -d|pg_restore|docker run|--apply\s*['"]|--prepare\s*['"]|--execute\s*['"]/i);
});
test('Windows parser and owner-host deny before network', {skip:process.platform!=='win32'},()=>{
 const parser="$t=$null;$e=$null;[System.Management.Automation.Language.Parser]::ParseFile('"+file+"',[ref]$t,[ref]$e)|Out-Null;if($e.Count){throw 'PS_PARSE_FAILED'}";
 const parse=spawnSync('powershell.exe',['-NoProfile','-NonInteractive','-Command',parser],{encoding:'utf8',timeout:15000});
 assert.equal(parse.status,0,parse.stderr+parse.stdout);
 for(const args of [[],['-Inspect']]) {
   const r=spawnSync('powershell.exe',['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',file,...args],{encoding:'utf8',timeout:15000});
   assert.equal(r.status,2,r.stdout+r.stderr);
   assert.match(r.stdout,/KMJ_P520_CANDIDATE_SOURCE_LAUNCH=BLOCKED_(?:EXPLICIT_INSPECT_REQUIRED|WRONG_P520_DEVICE)/);
   assert.doesNotMatch(r.stdout,/KMJ_P520_CANDIDATE_SOURCE_LAUNCH=REMOTE_READONLY_COMPLETE/);
 }
});
