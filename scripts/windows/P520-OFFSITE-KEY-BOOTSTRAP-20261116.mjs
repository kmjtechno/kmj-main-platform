#!/usr/bin/env node
// KMJ P520-only AGE X25519 recipient + Ed25519 receipt signer bootstrap.
// Private keys remain on the Windows P520. No cloud, no network, no upload.
// Owner-run only; NEVER run via unapproved CodeBridge generic Node gates.
import { generateKeyPairSync, sign, verify, createHash } from 'node:crypto';
import { existsSync, lstatSync, openSync, writeSync, closeSync, readFileSync } from 'node:fs';
import { basename, join } from 'node:path';
import os from 'node:os';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';

const PUB = /^age1[023456789acdefghjklmnpqrstuvwxyz]{58}$/;
export function validAgeRecipient(value) {
  return typeof value === 'string' && PUB.test(value);
}
export function isPrivateAcl(output) {
  if (typeof output !== 'string' || output.length > 8192) return false;
  const normalized = output.toLowerCase();
  if (!normalized.includes(':(f)') && !normalized.includes('(f)')) return false;
  // Deny broad group access regardless of localization of system user names.
  if (/(everyone|authenticated users|builtin\\users|\\guests|all application packages|s-1-1-0|s-1-5-11|s-1-5-32-545)/i.test(output)) {
    return false;
  }
  return true;
}
export function testSigner() {
  const { publicKey, privateKey } = generateKeyPairSync('ed25519');
  const payload = Buffer.from('kmj-p520-offsite-local-selftest', 'ascii');
  const signature = sign(null, payload, privateKey);
  if (signature.length !== 64 || !verify(null, payload, publicKey, signature)) throw new Error('SIGNER_TEST');
  if (verify(null, Buffer.from('tampered'), publicKey, signature)) throw new Error('TAMPER_ACCEPTED');
  return true;
}
function block(reason) {
  process.stdout.write('KMJ_P520_KEY_BOOTSTRAP=BLOCKED_' + reason + '\n');
  process.exitCode = 2;
}
function createExclusive(file, bytes, mode) {
  const fd = openSync(file, 'wx', mode);
  try { writeSync(fd, bytes); } finally { closeSync(fd); }
}
function provision() {
  if (process.platform !== 'win32' || os.hostname().toUpperCase() !== 'DESKTOP-5FVJMET') {
    return block('OWNER_WINDOWS_HOST');
  }
  const parent = process.env.LOCALAPPDATA;
  if (!parent || !existsSync(parent)) return block('LOCAL_APPDATA');
  const folder = join(parent, 'KMJ-Private-Offsite-Recovery');
  // Owner must first create a private directory with verified restricted ACL.
  // Never create keys in inherited/public directories.
  if (!existsSync(folder) || !lstatSync(folder).isDirectory() || lstatSync(folder).isSymbolicLink()) {
    return block('PRIVATE_KEY_DIRECTORY_NOT_PROVISIONED');
  }
  const acl = spawnSync('icacls.exe', [folder], { encoding: 'utf8', timeout: 12000, windowsHide: true });
  if (acl.status !== 0 || !isPrivateAcl(acl.stdout)) return block('PRIVATE_ACL_NOT_VERIFIED');
  const ageKey = join(folder, 'p520-offsite.agekey');
  const signer = join(folder, 'p520-receipt-signing-ed25519.pem');
  const signingPub = join(folder, 'p520-receipt-ed25519-public.pem');
  const agePub = join(folder, 'p520-age-recipient.txt');
  const files = [ageKey, signer, signingPub, agePub];
  if (files.some(existsSync)) return block('KEY_FILE_ALREADY_EXISTS_NO_CLOBBER');
  const check = spawnSync('age-keygen.exe', ['--version'], { encoding: 'utf8', timeout: 8000, windowsHide: true });
  if (check.status !== 0) return block('AGE_KEYGEN_NOT_AVAILABLE');
  const generated = spawnSync('age-keygen.exe', ['-o', ageKey], { encoding: 'utf8', timeout: 15000, windowsHide: true });
  if (generated.status !== 0 || !existsSync(ageKey)) return block('AGE_IDENTITY_GENERATION');
  const recipient = spawnSync('age-keygen.exe', ['-y', ageKey], { encoding: 'utf8', timeout: 10000, windowsHide: true });
  const publicValue = recipient.stdout?.trim();
  if (recipient.status !== 0 || !validAgeRecipient(publicValue)) return block('AGE_PUBLIC_RECIPIENT_VALIDATION');
  const { privateKey, publicKey } = generateKeyPairSync('ed25519');
  createExclusive(signer, Buffer.from(privateKey.export({ format: 'pem', type: 'pkcs8' }), 'ascii'), 0o600);
  const pub = Buffer.from(publicKey.export({ format: 'pem', type: 'spki' }), 'ascii');
  createExclusive(signingPub, pub, 0o600);
  createExclusive(agePub, Buffer.from(publicValue + '\n', 'ascii'), 0o600);
  process.stdout.write('KMJ_P520_KEY_BOOTSTRAP=GENERATED_PRIVATE_LOCAL_ONLY\n');
  process.stdout.write('P520_AGE_PUBLIC_RECIPIENT=' + publicValue + '\n');
  process.stdout.write('P520_SIGNING_PUBLIC_PEM_SHA256=' + createHash('sha256').update(pub).digest('hex') + '\n');
  process.stdout.write('PRIVATE_KEY_CONTENT_EXPOSED=NO\n');
  process.stdout.write('ELITE_OWNER_PIN_OF_PUBLIC_KEYS=REQUIRED\n');
  process.stdout.write('P520_OFFSITE_RECEIVE_AND_RESTORE=NOT_EXECUTED\n');
  process.stdout.write('PRODUCTION_APPROVAL=NOT_GRANTED\n');
}
const invoked = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
if (invoked) {
  if (process.argv.length !== 3) block('EXACT_MODE');
  else if (process.argv[2] === '--selftest') {
    testSigner();
    process.stdout.write('KMJ_P520_KEY_SELFTEST=PASS_NO_PERSISTENT_KEY\n');
  } else if (process.argv[2] === '--provision') provision();
  else block('EXACT_MODE');
}
