import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';

const file = 'scripts/windows/P520-MAIN-PLATFORM-OFFSITE-DOCTOR-20261116.ps1';
const src = readFileSync(file, 'utf8');

test('P520 doctor uses declared -Inspect only; StrictMode never reads uninitialized $args', () => {
  assert.match(src, /\[CmdletBinding\(\)\]/);
  assert.match(src, /param\(\[switch\]\$Inspect\)/);
  assert.match(src, /Set-StrictMode -Version Latest/);
  assert.match(src, /if \(-not \$Inspect\)/);
  assert.doesNotMatch(src, /\$args\b/i);
});

test('P520 doctor remains read-only and refuses non-owner host', () => {
  for (const marker of [
    'READ_ONLY_V1',
    'GOOGLE_VPS_DEPENDENCY=NONE',
    'P520_INDEPENDENT_DECRYPT_RESTORE=NOT_EXECUTED',
    'PRODUCTION_DB_MUTATION=NONE',
    'PRODUCTION_RELEASE_APPROVAL=NOT_GRANTED',
    'BLOCKED_WRONG_HOST'
  ]) assert.ok(src.includes(marker), marker);
  assert.doesNotMatch(src, /(?:Start|Restart|Enable|Stop)-ScheduledTask|Restart-Service|Start-Service|Remove-Item|Set-Content|git reset|git clean/i);
});

test('native Windows PowerShell parses the doctor and -Inspect reaches host gate without StrictMode error', { skip: process.platform !== 'win32' }, () => {
  const script = [
    "$ErrorActionPreference='Stop';",
    "$t=$null;$e=$null;",
    '[System.Management.Automation.Language.Parser]::ParseFile(',
    "'" + file + "',[ref]$t,[ref]$e)|Out-Null;",
    "if($e.Count -ne 0){throw 'PS_PARSE_FAILED'}"
  ].join(' ');
  const parsed = spawnSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command', script], { encoding: 'utf8', timeout: 15000 });
  assert.equal(parsed.status, 0, parsed.stderr + parsed.stdout);

  const missing = spawnSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', file], { encoding: 'utf8', timeout: 15000 });
  assert.equal(missing.status, 2, missing.stderr);
  assert.match(missing.stdout, /KMJ_P520_OFFSITE_DOCTOR=BLOCKED_INSPECT_ONLY/);

  const inspected = spawnSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', file, '-Inspect'], { encoding: 'utf8', timeout: 15000 });
  assert.equal(inspected.status, 2, inspected.stderr);
  assert.match(inspected.stdout, /KMJ_P520_OFFSITE_DOCTOR=BLOCKED_WRONG_HOST/);
  assert.doesNotMatch(inspected.stderr, /VariableIsUndefined|cannot be retrieved because it has not been set/i);
  assert.doesNotMatch(inspected.stdout, /P520_INDEPENDENT_DECRYPT_RESTORE=PASS/);
});

test('unknown parameter cannot bypass declared -Inspect contract', { skip: process.platform !== 'win32' }, () => {
  const r = spawnSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', file, '-Inspect', '-UnapprovedParam'], { encoding: 'utf8', timeout: 15000 });
  assert.notEqual(r.status, 0);
  assert.doesNotMatch(r.stdout, /READ_ONLY_V1/);
});
