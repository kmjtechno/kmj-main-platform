import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash, generateKeyPairSync } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import {
  Refuse, EXPECTED_AGE_RECIPIENT, EXPECTED_ED25519_PUBLIC_SHA,
  isAgePublicPair, attestSigningPair
} from './P520-OFFSITE-PUBLIC-IDENTITY-ATTEST-20261118.mjs';
const file='scripts/windows/P520-OFFSITE-PUBLIC-IDENTITY-ATTEST-20261118.mjs';

test('fixed P520 public recipient and Ed25519 pin match owner observation',()=>{
 assert.equal(EXPECTED_AGE_RECIPIENT,'age1jgk7wrgccyu8s7wlh6zpxnm4qdvfus0d5t092s9zkjjmtwe8efjstvcs5u');
 assert.equal(EXPECTED_ED25519_PUBLIC_SHA,'6216f2bc0bd7b63bea2f15bc771494fa6e2ab2fcfca01e75761a113120be81c4');
 assert.equal(isAgePublicPair(EXPECTED_AGE_RECIPIENT,EXPECTED_AGE_RECIPIENT+'\n'),true);
 for(const [recipient,saved] of [
  [EXPECTED_AGE_RECIPIENT.replace('age1','AGE1'), EXPECTED_AGE_RECIPIENT+'\n'],
  [EXPECTED_AGE_RECIPIENT, EXPECTED_AGE_RECIPIENT],
  [EXPECTED_AGE_RECIPIENT, 'age1'+'q'.repeat(58)+'\n'],
  [EXPECTED_AGE_RECIPIENT+'x', EXPECTED_AGE_RECIPIENT+'\n']
 ])assert.equal(isAgePublicPair(recipient,saved),false);
});

test('fresh Ed25519 key pair succeeds only with exact public PEM hash and matching private key',()=>{
 const pair=generateKeyPairSync('ed25519');
 const other=generateKeyPairSync('ed25519');
 const priv=Buffer.from(pair.privateKey.export({type:'pkcs8',format:'pem'}));
 const pub=Buffer.from(pair.publicKey.export({type:'spki',format:'pem'}));
 const outsider=Buffer.from(other.privateKey.export({type:'pkcs8',format:'pem'}));
 const pin=createHash('sha256').update(pub).digest('hex');
 assert.equal(attestSigningPair(priv,pub,pin),pin);
 assert.throws(()=>attestSigningPair(outsider,pub,pin),/SIGNER_PAIR_CHALLENGE_FAILED/);
 assert.throws(()=>attestSigningPair(priv,pub,'f'.repeat(64)),/SIGNER_OWNER_PUBLIC_PIN_MISMATCH/);
 assert.throws(()=>attestSigningPair(priv,pub,pin.slice(1)),/SIGNER_INPUT_INVALID/);
});

test('private material cannot be logged, copied, encrypted or sent; read-only P520 host gating',()=>{
 const src=readFileSync(file,'utf8');
 for(const marker of ['--inspect','PRIVATE_KEY_CONTENT_EXPOSED=NO',
   'ELITE_OWNER_PIN_OF_PUBLIC_KEYS=NOT_YET_VERIFIED',
   'P520_INDEPENDENT_RESTORE=NOT_EXECUTED',
   'PRODUCTION_APPROVAL=NOT_GRANTED',
   'verifyWindowsPrivateAcl','AGE_PRIVATE_FILE_ACL_UNTRUSTED']) {
   assert.ok(src.includes(marker),marker);
 }
 assert.doesNotMatch(src,/writeFileSync|createWriteStream|unlinkSync|chmodSync|chownSync|git reset|git clean|ssh |sftp |https?\.request|(?:fetch|axios)\(/);
 const r=spawnSync(process.execPath,[file,'--inspect'],{encoding:'utf8',timeout:15000});
 assert.equal(r.status,2);
 assert.match(r.stdout,/P520_READONLY_PUBLIC_IDENTITY_ATTEST=BLOCKED_WRONG_OWNER_P520_HOST/);
 assert.doesNotMatch(r.stdout,/BEGIN PRIVATE KEY|AGE-SECRET-KEY/);
});
