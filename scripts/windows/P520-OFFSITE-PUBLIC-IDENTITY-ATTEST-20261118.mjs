#!/usr/bin/env node
// P520 owner-only READ ONLY proof: correlate locally generated AGE and Ed25519
// public identities with their private counterparts and owner-observed pins.
// Do not copy or print private keys, start services, pin remote authority,
// upload data, encrypt backups, create receipts, or approve production.
import { createHash, createPrivateKey, createPublicKey, randomBytes, sign, verify } from 'node:crypto';
import { lstatSync, readFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import { verifyWindowsPrivateAcl } from './P520-OFFSITE-ACL-VERIFY-20261116.mjs';

export const EXPECTED_AGE_RECIPIENT =
  'age1jgk7wrgccyu8s7wlh6zpxnm4qdvfus0d5t092s9zkjjmtwe8efjstvcs5u';
export const EXPECTED_ED25519_PUBLIC_SHA =
  '6216f2bc0bd7b63bea2f15bc771494fa6e2ab2fcfca01e75761a113120be81c4';
const AGE_RECIPIENT = /^age1[023456789acdefghjklmnpqrstuvwxyz]{58}$/;
const SHA256 = /^[a-f0-9]{64}$/;

export class Refuse extends Error {}

export function isAgePublicPair(actualFromPrivate, savedPublic, expected = EXPECTED_AGE_RECIPIENT) {
  return AGE_RECIPIENT.test(actualFromPrivate) &&
    actualFromPrivate === expected &&
    savedPublic === expected + '\n';
}

export function attestSigningPair(privateBytes, publicBytes, expected = EXPECTED_ED25519_PUBLIC_SHA) {
  if (!Buffer.isBuffer(privateBytes) || !Buffer.isBuffer(publicBytes) ||
    !SHA256.test(expected) || privateBytes.length < 64 || privateBytes.length > 8192 ||
    publicBytes.length < 64 || publicBytes.length > 4096) {
    throw new Refuse('SIGNER_INPUT_INVALID');
  }
  const fingerprint = createHash('sha256').update(publicBytes).digest('hex');
  if (fingerprint !== expected) throw new Refuse('SIGNER_OWNER_PUBLIC_PIN_MISMATCH');
  const secret = createPrivateKey(privateBytes);
  const publicKey = createPublicKey(publicBytes);
  if (secret.asymmetricKeyType !== 'ed25519' || publicKey.asymmetricKeyType !== 'ed25519') {
    throw new Refuse('SIGNER_ALGORITHM_INVALID');
  }
  const message = Buffer.concat([Buffer.from('kmj-p520-private-local-proof-v1\0'), randomBytes(32)]);
  const signature = sign(null, message, secret);
  if (signature.length !== 64 || !verify(null, message, publicKey, signature) ||
    verify(null, Buffer.concat([message,Buffer.from('tampered')]), publicKey, signature)) {
    throw new Refuse('SIGNER_PAIR_CHALLENGE_FAILED');
  }
  return fingerprint;
}

function plainFile(file, max) {
  const stat = lstatSync(file);
  if (!stat.isFile() || stat.isSymbolicLink() || stat.nlink !== 1 ||
    stat.size < 32 || stat.size > max) throw new Refuse('PUBLIC_PROOF_FILE_METADATA');
  if (!verifyWindowsPrivateAcl(file)) throw new Refuse('PRIVATE_KEY_OR_PUBLIC_FILE_ACL_UNTRUSTED');
  return readFileSync(file);
}

function main(args) {
  if (args.length !== 1 || args[0] !== '--inspect') throw new Refuse('EXACT_INSPECT_REQUIRED');
  if (process.platform !== 'win32' || os.hostname().toUpperCase() !== 'DESKTOP-5FVJMET') {
    throw new Refuse('WRONG_OWNER_P520_HOST');
  }
  const base=process.env.LOCALAPPDATA;
  if (!base || !path.win32.isAbsolute(base)) throw new Refuse('LOCAL_APPDATA_UNAVAILABLE');
  const folder=path.join(base,'KMJ-Private-Offsite-Recovery');
  const inbox=path.join(folder,'inbox');
  for (const candidate of [folder,inbox]) {
    const st=lstatSync(candidate);
    if (!st.isDirectory() || st.isSymbolicLink() ||
      !verifyWindowsPrivateAcl(candidate)) throw new Refuse('PRIVATE_DIRECTORY_ACL_UNTRUSTED');
  }
  const ageKey=path.join(folder,'p520-offsite.agekey');
  // The AGE private key is NEVER read by this script: age-keygen -y derives only public.
  const ageStat=lstatSync(ageKey);
  if (!ageStat.isFile() || ageStat.isSymbolicLink() || ageStat.nlink !== 1 ||
    ageStat.size < 40 || ageStat.size > 8192 || !verifyWindowsPrivateAcl(ageKey)) {
    throw new Refuse('AGE_PRIVATE_FILE_ACL_UNTRUSTED');
  }
  const agePublic=plainFile(path.join(folder,'p520-age-recipient.txt'),256).toString('ascii');
  const recipient=spawnSync('age-keygen.exe',['-y',ageKey],{
    encoding:'utf8',timeout:15000,maxBuffer:2048,windowsHide:true
  });
  if (recipient.status !== 0 || recipient.error || !isAgePublicPair(recipient.stdout?.trim(),agePublic)) {
    throw new Refuse('AGE_OWNER_PUBLIC_PAIR_MISMATCH');
  }
  console.log('P520_AGE_PRIVATE_PUBLIC_PAIR=PASS');
  const signer=plainFile(path.join(folder,'p520-receipt-signing-ed25519.pem'),8192);
  const pub=plainFile(path.join(folder,'p520-receipt-ed25519-public.pem'),4096);
  const pin=attestSigningPair(signer,pub);
  console.log('P520_ED25519_PRIVATE_PUBLIC_PAIR=PASS');
  console.log('P520_PRIVATE_FILES_ACL=PASS');
  console.log('P520_AGE_PUBLIC_RECIPIENT='+EXPECTED_AGE_RECIPIENT);
  console.log('P520_SIGNING_PUBLIC_PEM_SHA256='+pin);
  console.log('PRIVATE_KEY_CONTENT_EXPOSED=NO');
  console.log('ELITE_OWNER_PIN_OF_PUBLIC_KEYS=NOT_YET_VERIFIED');
  console.log('P520_NEW_CANDIDATE_ENCRYPTED_BACKUP=NOT_YET_VERIFIED');
  console.log('P520_INDEPENDENT_RESTORE=NOT_EXECUTED');
  console.log('PRODUCTION_APPROVAL=NOT_GRANTED');
  console.log('P520_READONLY_PUBLIC_IDENTITY_ATTEST=PASS');
}

if(process.argv[1] && import.meta.url===pathToFileURL(process.argv[1]).href) {
  try { main(process.argv.slice(2)); }
  catch(e) {
    const msg= e instanceof Refuse ? e.message : 'PRIVATE_IDENTITY_INSPECTION_FAILED';
    console.log('P520_READONLY_PUBLIC_IDENTITY_ATTEST=BLOCKED_'+msg);
    console.log('PRIVATE_KEY_CONTENT_EXPOSED=NO');
    console.log('PRODUCTION_APPROVAL=NOT_GRANTED');
    process.exitCode=2;
  }
}
