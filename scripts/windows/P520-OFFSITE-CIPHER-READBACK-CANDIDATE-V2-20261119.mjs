#!/usr/bin/env node
// Fixed P520 encrypted offsite artifact SHA256 readback; no decryption or release.
import { createHash } from 'node:crypto';
import { constants, closeSync, fstatSync, lstatSync, openSync, readSync, statSync } from 'node:fs';
import { join } from 'node:path';
import os from 'node:os';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import { verifyWindowsPrivateAcl } from './P520-OFFSITE-ACL-VERIFY-20261116.mjs';

export const NAME = 'offsite-p520-bd8975f0ee88.tar.gz.age';
export const MAX_BYTES = 10 * 1024 ** 3;
const SHA = /^[0-9a-f]{64}$/;
export class Refuse extends Error {}

function pathInfo(path) {
  const v = lstatSync(path);
  if (!v.isDirectory() || v.isSymbolicLink()) throw new Refuse('PRIVATE_DIRECTORY_UNSAFE');
}
export function fixedRecoveryPath(localAppData) {
  if (typeof localAppData !== 'string' || !localAppData.trim()) throw new Refuse('LOCAL_APPDATA_UNAVAILABLE');
  const parent = join(localAppData, 'KMJ-Private-Offsite-Recovery');
  const inbox = join(parent, 'inbox');
  for (const path of [localAppData, parent, inbox]) pathInfo(path);
  return { parent, inbox, cipher: join(inbox, NAME) };
}
export function verifyCipher(cipher, digest, expectedBytes) {
  if (!SHA.test(digest) || !Number.isSafeInteger(expectedBytes) ||
      expectedBytes < 256 || expectedBytes > MAX_BYTES) {
    throw new Refuse('EXPECTED_DIGEST_OR_SIZE_INVALID');
  }
  const initial = lstatSync(cipher, { bigint: true });
  if (!initial.isFile() || initial.isSymbolicLink() || initial.nlink !== 1n ||
      initial.size !== BigInt(expectedBytes)) {
    throw new Refuse('CIPHER_PATH_OR_METADATA');
  }
  // O_NOFOLLOW prevents last-component symlink races on platforms supporting it;
  // fstat must agree with the original file identity and size.
  const flags = constants.O_RDONLY | (constants.O_NOFOLLOW || 0);
  const fd = openSync(cipher, flags);
  try {
    const st = fstatSync(fd, { bigint: true });
    if (!st.isFile() || st.nlink !== 1n || st.size !== BigInt(expectedBytes) ||
        st.dev !== initial.dev || st.ino !== initial.ino) {
      throw new Refuse('CIPHER_CHANGED_DURING_OPEN');
    }
    const hash = createHash('sha256');
    const buf = Buffer.allocUnsafe(256 * 1024);
    let read = 0;
    while (read < expectedBytes) {
      const n = readSync(fd, buf, 0, Math.min(buf.length, expectedBytes - read), null);
      if (!n) throw new Refuse('CIPHER_TRUNCATED');
      hash.update(buf.subarray(0, n));
      read += n;
    }
    const atEnd = readSync(fd, buf, 0, 1, null);
    const after = fstatSync(fd, { bigint: true });
    if (atEnd !== 0 || after.dev !== st.dev || after.ino !== st.ino ||
        after.size !== st.size || after.mtimeNs !== st.mtimeNs ||
        after.ctimeNs !== st.ctimeNs) {
      throw new Refuse('CIPHER_MUTATED_DURING_READ');
    }
    if (hash.digest('hex') !== digest) throw new Refuse('CIPHER_SHA256_MISMATCH');
    return { sha256: digest, bytes: read, hostReadback: true };
  } finally {
    closeSync(fd);
  }
}
function ensurePrivateAcl(path) {
  if (!verifyWindowsPrivateAcl(path)) throw new Refuse('PRIVATE_ACL_NOT_VERIFIED');
}
function block(reason) {
  const msg = /^[A-Z0-9_]+$/.test(reason) ? reason : 'UNCLASSIFIED';
  process.stdout.write('KMJ_P520_CIPHER_READBACK=BLOCKED_' + msg + '\n');
  process.stdout.write('P520_INDEPENDENT_DECRYPT_RESTORE=NOT_EXECUTED\n');
  process.stdout.write('PRODUCTION_APPROVAL=NOT_GRANTED\n');
  process.exitCode = 2;
}
function main(args) {
  if (args.length !== 5 || args[0] !== '--verify' || args[1] !== '--sha256' ||
      args[3] !== '--bytes' || !SHA.test(args[2]) ||
      !/^[1-9][0-9]{2,10}$/.test(args[4])) {
    return block('EXACT_DIGEST_SIZE_ARGS');
  }
  if (process.platform !== 'win32' || os.hostname().toUpperCase() !== 'DESKTOP-5FVJMET') {
    return block('WRONG_P520_HOST');
  }
  try {
    const path = fixedRecoveryPath(process.env.LOCALAPPDATA);
    ensurePrivateAcl(path.parent);
    ensurePrivateAcl(path.inbox);
    const result = verifyCipher(path.cipher, args[2], Number(args[4]));
    process.stdout.write('KMJ_P520_CIPHER_READBACK=PASS\n');
    process.stdout.write('CANDIDATE_SHA=bd8975f0ee888a26013a6669e687db540f39f440\n');
    process.stdout.write('RECEIVED_CIPHER_SHA256=' + result.sha256 + '\n');
    process.stdout.write('RECEIVED_CIPHER_BYTES=' + result.bytes + '\n');
    process.stdout.write('P520_INDEPENDENT_DECRYPT_RESTORE=NOT_EXECUTED\n');
    process.stdout.write('PRODUCTION_APPROVAL=NOT_GRANTED\n');
  } catch (e) {
    block(e instanceof Refuse ? e.message : 'FILESYSTEM_UNAVAILABLE');
  }
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main(process.argv.slice(2));
}
