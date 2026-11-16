#!/usr/bin/env node
// P520 exact encrypted backup inbox finalizer; NO transfer, key or decryption.
// Owner's trusted transport writes only the exact .partial basename; this tool
// checks SHA/size and safely finalizes with a NO-CLOBBER hardlink on NTFS.
import { linkSync, lstatSync, statSync, unlinkSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import os from 'node:os';
import { pathToFileURL } from 'node:url';
import { NAME, MAX_BYTES, Refuse, fixedRecoveryPath, verifyCipher } from './P520-OFFSITE-CIPHER-READBACK-20261116.mjs';
import { verifyWindowsPrivateAcl } from './P520-OFFSITE-ACL-VERIFY-20261116.mjs';

const SHA = /^[a-f0-9]{64}$/;

export function finalizeInbox(inbox, sha, bytes) {
  if (!SHA.test(sha) || !Number.isSafeInteger(bytes) ||
      bytes < 256 || bytes > MAX_BYTES) throw new Refuse('EXPECTED_DIGEST_OR_SIZE_INVALID');
  const partial = join(inbox, NAME + '.partial');
  const target = join(inbox, NAME);
  // Never replace, repair or delete existing final objects. A verified final
  // object is idempotent only if there is no ambiguous staged partial.
  if (existsSync(target) || lstatMaybe(target)) {
    if (existsSync(partial) || lstatMaybe(partial)) throw new Refuse('AMBIGUOUS_PARTIAL_AND_FINAL');
    verifyCipher(target, sha, bytes);
    return { result: 'ALREADY_PRESENT_EXACT_SHA', ...verifyCipher(target, sha, bytes) };
  }
  // Refuse anything but the exact private partial object; verify full content
  // before linking. linkSync refuses an existing final path (O_EXCL-style).
  verifyCipher(partial, sha, bytes);
  try {
    linkSync(partial, target);
  } catch (e) {
    throw new Refuse(e?.code === 'EEXIST' ? 'FINAL_EXISTS_NO_CLOBBER' : 'FINAL_HARDLINK_FAILED');
  }
  const a = statSync(partial, { bigint: true });
  const b = statSync(target, { bigint: true });
  if (a.ino !== b.ino || a.dev !== b.dev ||
      a.nlink !== 2n || b.nlink !== 2n ||
      a.size !== BigInt(bytes) || b.size !== BigInt(bytes)) {
    // No cleanup: preserve evidence of unsafe host filesystem behavior.
    throw new Refuse('FINAL_LINK_IDENTITY_UNVERIFIED');
  }
  // Only now discard the exact partial hardlink; resulting final must have
  // link-count ONE, independently hashed from its final name.
  unlinkSync(partial);
  const result = verifyCipher(target, sha, bytes);
  return { result: 'FINALIZED_NO_CLOBBER', ...result };
}

function lstatMaybe(file) {
  try { lstatSync(file); return true; }
  catch (e) { if (e?.code === 'ENOENT') return false; throw e; }
}
function ensurePrivateAcl(path) {
  if (!verifyWindowsPrivateAcl(path)) throw new Refuse('INBOX_PRIVATE_ACL_UNVERIFIED');
}
function deny(code) {
  process.stdout.write('KMJ_P520_INBOX_FINALIZE=BLOCKED_' +
    (/^[A-Z0-9_]+$/.test(code) ? code : 'UNCLASSIFIED') + '\n');
  process.stdout.write('P520_DECRYPT_AND_DATABASE_RESTORE=NOT_EXECUTED\n');
  process.stdout.write('PRODUCTION_APPROVAL=NOT_GRANTED\n');
  process.exitCode = 2;
}
function main(args) {
  if (args.length !== 5 || args[0] !== '--finalize' || args[1] !== '--sha256' ||
      args[3] !== '--bytes' || !SHA.test(args[2]) ||
      !/^[1-9][0-9]{2,10}$/.test(args[4])) {
    return deny('EXACT_ARGS');
  }
  if (process.platform !== 'win32' || os.hostname().toUpperCase() !== 'DESKTOP-5FVJMET') {
    return deny('WRONG_P520_HOST');
  }
  try {
    const { parent, inbox } = fixedRecoveryPath(process.env.LOCALAPPDATA);
    ensurePrivateAcl(parent);
    ensurePrivateAcl(inbox);
    const r = finalizeInbox(inbox, args[2], Number(args[4]));
    process.stdout.write('KMJ_P520_INBOX_FINALIZE=' + r.result + '\n');
    process.stdout.write('P520_CIPHER_SHA256=EXACT_MATCH\n');
    process.stdout.write('P520_CIPHER_BYTES=' + r.bytes + '\n');
    process.stdout.write('P520_INDEPENDENT_DECRYPT_AND_RESTORE=NOT_EXECUTED\n');
    process.stdout.write('PRODUCTION_APPROVAL=NOT_GRANTED\n');
  } catch (error) {
    return deny(error instanceof Refuse ? error.message : 'FILESYSTEM_OR_ACL_UNAVAILABLE');
  }
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main(process.argv.slice(2));
}
