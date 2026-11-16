import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, linkSync, mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import os from 'node:os';
import { NAME, Refuse, verifyCipher } from './P520-OFFSITE-CIPHER-READBACK-20261116.mjs';
import { finalizeInbox } from './P520-OFFSITE-INBOX-FINALIZE-20261116.mjs';

function fixture(action, withPartial=true) {
  const folder = mkdtempSync(join(os.tmpdir(), 'kmj-p520-inbox-'));
  const inbox = join(folder, 'inbox');
  mkdirSync(inbox);
  const partial = join(inbox, NAME + '.partial'), target = join(inbox, NAME);
  const bytes = Buffer.concat([Buffer.from('age-encryption.org/v1\n'), Buffer.alloc(1000, 0x77)]);
  const sha = createHash('sha256').update(bytes).digest('hex');
  if (withPartial) writeFileSync(partial, bytes);
  try { return action({ inbox, partial, target, sha, bytes }); }
  finally { rmSync(folder, { recursive:true, force:true }); }
}
test('exact private partial finalizes without overwrite; second call idempotent', () => fixture(f => {
  const x = finalizeInbox(f.inbox, f.sha, f.bytes.length);
  assert.equal(x.result, 'FINALIZED_NO_CLOBBER');
  assert.equal(existsSync(f.partial), false);
  assert.equal(readFileSync(f.target).compare(f.bytes), 0);
  assert.equal(statSync(f.target).nlink, 1);
  assert.equal(finalizeInbox(f.inbox, f.sha, f.bytes.length).result, 'ALREADY_PRESENT_EXACT_SHA');
}));
test('wrong digest, size and malformed digest never delete a partial object', () => fixture(f => {
  for (const [sha, bytes] of [['a'.repeat(64), f.bytes.length],
     [f.sha, f.bytes.length-1], ['INVALID', f.bytes.length],
     [f.sha, 255], [f.sha, 10*1024**3+1]]) {
    assert.throws(() => finalizeInbox(f.inbox, sha, bytes));
    assert.equal(existsSync(f.partial), true);
    assert.equal(existsSync(f.target), false);
  }
}));
test('no-clobber: incorrect existing target is kept unchanged', () => fixture(f => {
  const old = Buffer.alloc(f.bytes.length, 0x11);
  writeFileSync(f.target, old);
  assert.throws(() => finalizeInbox(f.inbox, f.sha, f.bytes.length), /AMBIGUOUS_PARTIAL_AND_FINAL/);
  assert.deepEqual(readFileSync(f.target), old);
  assert.deepEqual(readFileSync(f.partial), f.bytes);
}));
test('partial symlink refused without following or clobbering', () => fixture(f => {
  rmSync(f.partial);
  symlinkSync('/etc/passwd', f.partial);
  assert.throws(() => finalizeInbox(f.inbox, f.sha, f.bytes.length));
  assert.equal(existsSync(f.target), false);
}));
test('partial hardlink refused to avoid aliasing unsafe source', () => fixture(f => {
  linkSync(f.partial, join(f.inbox, 'other'));
  assert.throws(() => finalizeInbox(f.inbox, f.sha, f.bytes.length), /CIPHER_PATH_OR_METADATA/);
}));
test('invalid direct argv must block before touching host or files', () => {
  const executable='scripts/windows/P520-OFFSITE-INBOX-FINALIZE-20261116.mjs';
  for (const args of [[], ['--help'], ['--finalize'], ['--finalize','--sha256','X'.repeat(64),'--bytes','500']]) {
    const r=spawnSync(process.execPath, [executable,...args],{encoding:'utf8',timeout:10000});
    assert.equal(r.status, 2);
    assert.match(r.stdout,/BLOCKED_EXACT_ARGS/);
    assert.match(r.stdout,/PRODUCTION_APPROVAL=NOT_GRANTED/);
  }
});
