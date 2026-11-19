import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';

const file='scripts/windows/P520-OWNER-ONLY-KEY-FILE-OWNER-REPAIR-20261118.ps1';
const src=readFileSync(file,'utf8');
test('owner-only operation is explicitly gated and never touches private key bytes or ACL grants',()=>{
  for(const marker of [
    '[CmdletBinding()]','param([switch]$Inspect,[switch]$Repair)',
    'DESKTOP-5FVJMET','EXACT_ONE_MODE_REQUIRED','UNTRUSTED_FILE_OWNER',
    'CURRENT_OWNER_ACCOUNT_LACKS_FULL_ACCESS','P520_FILE_SET_PRECHECK',
    'P520_DACL_GRANTS_OR_INHERITANCE_CHANGED','P520_KEY_CONTENT_READ_OR_REPLACED',
    'P520_OWNER_REPAIR','P520_HOST_MUTATION',
    'P520_CODEBRIDGE_OR_PRODUCTION','NOT_GRANTED',
    'P520_FILE_OWNER_ONLY_REPAIRED','/setowner'
  ]) assert.ok(src.includes(marker),marker);
  for(const name of [
    'p520-offsite.agekey','p520-age-recipient.txt',
    'p520-receipt-signing-ed25519.pem','p520-receipt-ed25519-public.pem'
  ])assert.ok(src.includes(name),name);
  assert.doesNotMatch(src, /(?<!# )\b(?:Get-Content|Set-Content|ReadAllText|WriteAllText|ReadAllBytes|WriteAllBytes|Copy-Item|Move-Item|Remove-Item|New-Item|Set-Acl|SetAccessRuleProtection|docker\.exe|age-keygen\.exe|regenerate|git reset|git clean)\b/i);
  assert.doesNotMatch(src, /&\s*\$aclExe[^\r\n]*(?:\/grant|\/reset|\/inheritance|\/deny|\/T\b)/i);
  assert.match(src,/if\(\$owner -cnotin \$allowed\)/);
  assert.match(src,/if\(\$after.Owner -cne \$mySid -or \$after.Snapshot -cne \$entry.Before.Snapshot -or/);
});
test('native Windows PowerShell parser, host guard, and mandatory explicit mode', {skip:process.platform!=='win32'},()=>{
  const parser="$tokens=$null;$errors=$null;[System.Management.Automation.Language.Parser]::ParseFile('"+file+"',[ref]$tokens,[ref]$errors)|Out-Null;if($errors.Count -gt 0){throw 'SCRIPT_PARSER_ERROR'}";
  const syntax=spawnSync('powershell.exe',['-NoProfile','-NonInteractive','-Command',parser],{encoding:'utf8',timeout:15000});
  assert.equal(syntax.status,0,syntax.stdout+syntax.stderr);
  for (const flags of [[], ['-Inspect'], ['-Repair'], ['-Repair','-Inspect']]) {
    const result=spawnSync('powershell.exe',['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',file,...flags],{encoding:'utf8',timeout:15000});
    assert.equal(result.status,2,result.stdout+result.stderr);
    assert.match(result.stdout,/P520_OWNER_REPAIR=BLOCKED_(?:EXACT_ONE_MODE_REQUIRED|WRONG_P520_OWNER_DEVICE)/);
    assert.doesNotMatch(result.stdout,/P520_OWNER_REPAIR=PASS/);
  }
});
