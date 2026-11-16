import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { validAgeRecipient, isPrivateAcl, testSigner } from './P520-OFFSITE-KEY-BOOTSTRAP-20261116.mjs';

test('ed25519 signing and tamper refusal without creating keys on disk', () => {
  assert.equal(testSigner(), true);
});
test('recipient format and data containment', () => {
  assert.equal(validAgeRecipient('age1' + 'q'.repeat(58)), true);
  for (const invalid of ['age1', 'AGE1' + 'q'.repeat(58), 'age1' + 'O'.repeat(58), 'age1' + 'q'.repeat(59), 'AGE-SECRET-KEY-1' + 'q'.repeat(60)]) {
    assert.equal(validAgeRecipient(invalid), false);
  }
});
test('ACL rejects broad principals', () => {
  assert.equal(isPrivateAcl('P520\\Owner:(F)\nNT AUTHORITY\\SYSTEM:(F)'), true);
  for (const acl of ['BUILTIN\\Users:(RX)\nP520\\Owner:(F)',
      'Everyone:(F)', 'Authenticated Users:(R)', 'S-1-1-0:(F)',
      'BUILTIN\\Guests:(R)', 'ALL APPLICATION PACKAGES:(RX)', '']) {
    assert.equal(isPrivateAcl(acl), false);
  }
});
test('no commands except --selftest and P520 gated provisioning', () => {
  const p = spawnSync(process.execPath, ['scripts/windows/P520-OFFSITE-KEY-BOOTSTRAP-20261116.mjs', '--help'],
    { encoding:'utf8', timeout:10000 });
  assert.equal(p.status, 2);
  assert.match(p.stdout, /BLOCKED_EXACT_MODE/);
});
test('selftest never provisions a persistent key or accesses the network', () => {
  const p = spawnSync(process.execPath, ['scripts/windows/P520-OFFSITE-KEY-BOOTSTRAP-20261116.mjs', '--selftest'],
    { encoding:'utf8', timeout:10000 });
  assert.equal(p.status, 0);
  assert.match(p.stdout, /PASS_NO_PERSISTENT_KEY/);
});
