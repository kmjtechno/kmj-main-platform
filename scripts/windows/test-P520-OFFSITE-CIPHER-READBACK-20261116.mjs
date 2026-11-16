import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { chmodSync, linkSync, mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import { join } from 'node:path';
import { NAME, Refuse, fixedRecoveryPath, verifyCipher } from './P520-OFFSITE-CIPHER-READBACK-20261116.mjs';

function fixture(fn) {
  const root = mkdtempSync(join(os.tmpdir(), 'kmj-cipher-readback-'));
  try {
    const parent = join(root, 'KMJ-Private-Offsite-Recovery');
    const inbox = join(parent, 'inbox');
    mkdirSync(parent);
    mkdirSync(inbox);
    const path = join(inbox, NAME);
    const data = Buffer.concat([Buffer.from('age-encryption.org/v1\n'), Buffer.alloc(850, 0x7b)]);
    const sha = createHash('sha256').update(data).digest('hex');
    writeFileSync(path, data);
    return fn({ root, path, inbox, data, sha, bytes: data.length });
  } finally {
    rmSync(root, { force: true, recursive: true });
  }
}
test('streaming cipher readback PASS exact size and SHA, never restoration', () => fixture(f => {
  assert.deepEqual(verifyCipher(f.path, f.sha, f.bytes),
    { sha256: f.sha, bytes: f.bytes, hostReadback: true });
  const path = fixedRecoveryPath(f.root);
  assert.equal(path.cipher, f.path);
}));
test('tampered and forged bytes fail even when length unchanged', () => fixture(f => {
  writeFileSync(f.path, Buffer.alloc(f.bytes, 0x17));
  assert.throws(() => verifyCipher(f.path, f.sha, f.bytes), /CIPHER_SHA256_MISMATCH/);
}));
test('size and digest arguments are exact', () => fixture(f => {
  for (const d of ['A'.repeat(64), '0'.repeat(63), '', 'f'.repeat(65)]) {
    assert.throws(() => verifyCipher(f.path, d, f.bytes), /EXPECTED_DIGEST_OR_SIZE_INVALID/);
  }
  for (const b of [0, 255, 10*1024**3+1, 1.5, '1000']) {
    assert.throws(() => verifyCipher(f.path, f.sha, b), /EXPECTED_DIGEST_OR_SIZE_INVALID/);
  }
  assert.throws(() => verifyCipher(f.path, f.sha, f.bytes-1), /CIPHER_PATH_OR_METADATA/);
}));
test('symlink and hardlink ciphertext blocked before opening', () => fixture(f => {
  const sym = join(f.inbox, 'sym.age');
  symlinkSync(f.path, sym);
  assert.throws(() => verifyCipher(sym, f.sha, f.bytes), /CIPHER_PATH_OR_METADATA/);
  const hard = join(f.inbox, 'hard.age');
  linkSync(f.path, hard);
  assert.throws(() => verifyCipher(f.path, f.sha, f.bytes), /CIPHER_PATH_OR_METADATA/);
}));
test('parent or inbox symlink refusal', () => fixture(f => {
  assert.equal(fixedRecoveryPath(f.root).cipher, f.path);
  const other = join(f.root, 'linked');
  symlinkSync(f.inbox, other, 'dir');
  assert.throws(() => fixedRecoveryPath(join(f.root, 'missing')), /PRIVATE_DIRECTORY_UNSAFE|ENOENT/);
}));
test('invalid CLI refuses before path inspection or network', () => {
  const path = 'scripts/windows/P520-OFFSITE-CIPHER-READBACK-20261116.mjs';
  for (const args of [[], ['--help'], ['--verify'], ['--verify','--sha256','bad','--bytes','1000']]) {
    const child = spawnSync(process.execPath, [path, ...args], { encoding: 'utf8', timeout: 10000 });
    assert.equal(child.status, 2);
    assert.match(child.stdout, /BLOCKED_EXACT_DIGEST_SIZE_ARGS/);
    assert.match(child.stdout, /PRODUCTION_APPROVAL=NOT_GRANTED/);
  }
});
