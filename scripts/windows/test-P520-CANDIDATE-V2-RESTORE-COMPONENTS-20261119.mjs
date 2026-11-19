// Synthetic-only verification of the new candidate-bound P520 runner and
// receipt. NO P520 keys, Docker containers, production data or deployment.
import assert from 'node:assert/strict';
import test from 'node:test';
import { createHash, generateKeyPairSync, sign, verify } from 'node:crypto';
import { mkdtempSync, rmSync, writeFileSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

import { NAME, verifyCipher, fixedRecoveryPath } from './P520-OFFSITE-CIPHER-READBACK-CANDIDATE-V2-20261119.mjs';
import { finalizeInbox } from './P520-OFFSITE-INBOX-FINALIZE-CANDIDATE-V2-20261119.mjs';
import { parseArgv } from './P520-OFFSITE-CONTAINER-ADMISSION-CANDIDATE-V2-20261119.mjs';
import { buildReceipt, signVerifiedPayload } from './P520-OFFSITE-SIGNED-RESTORE-RECEIPT-CANDIDATE-V2-20261119.mjs';
import { RESTORE_PY, pgStorageArgs } from './P520-OFFSITE-PG-STORAGE-RESTORE-CANDIDATE-V2-20261119.mjs';
import { VALIDATION_PY, args, decryptArgs, validateArgs } from './P520-OFFSITE-BUNDLE-ISOLATION-CANDIDATE-V2-20261119.mjs';

const CANDIDATE='bd8975f0ee888a26013a6669e687db540f39f440';
const OLD='4c9d59103b99a6cfe675bb7b8961fc956eb294f0';
const PREVIOUS='platform-ce6ad7dc9d89';
const HEX64='a'.repeat(64);
const components=[
'P520-OFFSITE-CIPHER-READBACK-CANDIDATE-V2-20261119.mjs',
'P520-OFFSITE-INBOX-FINALIZE-CANDIDATE-V2-20261119.mjs',
'P520-OFFSITE-CONTAINER-ADMISSION-CANDIDATE-V2-20261119.mjs',
'P520-OFFSITE-PG-STORAGE-RESTORE-CANDIDATE-V2-20261119.mjs',
'P520-OFFSITE-SIGNED-RESTORE-RECEIPT-CANDIDATE-V2-20261119.mjs',
'P520-OFFSITE-BUNDLE-ISOLATION-CANDIDATE-V2-20261119.mjs'];

test('all six candidate-bound sources exclude old 4C9 evidence and import no V1 restore modules',()=>{
  for(const name of components){
    const src=readFileSync(fileURLToPath(new URL('./'+name,import.meta.url)),'utf8');
    assert.ok(!src.includes(OLD),name);
    assert.doesNotMatch(src,/\b(?:P520-OFFSITE-CIPHER-READBACK|P520-OFFSITE-CONTAINER-ADMISSION|P520-OFFSITE-PG-STORAGE-RESTORE|P520-OFFSITE-SIGNED-RESTORE-RECEIPT)-20261116\.mjs/);
    assert.doesNotMatch(src,/docker(?:\.exe)?\s+(?:pull|build)|--pull=always|--network=host/i);
  }
  assert.equal(NAME,'offsite-p520-bd8975f0ee88.tar.gz.age');
  assert.ok(RESTORE_PY.includes(CANDIDATE));
  assert.ok(VALIDATION_PY.includes(CANDIDATE));
  assert.ok(RESTORE_PY.includes(PREVIOUS));
  assert.ok(VALIDATION_PY.includes(PREVIOUS));
  assert.ok(!RESTORE_PY.includes(OLD));
  assert.ok(!VALIDATION_PY.includes(OLD));
});

test('cipher readback checks full digest and encrypted inbox no-clobber finalizer',()=>{
  const root=mkdtempSync(join(tmpdir(),'kmj-p520-v2-cipher-'));
  try{
    const partial=join(root,NAME+'.partial');
    const cipher=Buffer.alloc(512,17);
    const digest=createHash('sha256').update(cipher).digest('hex');
    writeFileSync(partial,cipher,{flag:'wx'});
    assert.deepEqual(verifyCipher(partial,digest,cipher.length),{sha256:digest,bytes:cipher.length,hostReadback:true});
    assert.throws(()=>verifyCipher(partial,'0'.repeat(64),cipher.length),/CIPHER_SHA256_MISMATCH/);
    const first=finalizeInbox(root,digest,cipher.length);
    assert.equal(first.result,'FINALIZED_NO_CLOBBER');
    assert.equal(verifyCipher(join(root,NAME),digest,cipher.length).bytes,cipher.length);
    const again=finalizeInbox(root,digest,cipher.length);
    assert.equal(again.result,'ALREADY_PRESENT_EXACT_SHA');
    assert.throws(()=>verifyCipher(join(root,NAME),digest,999),/CIPHER_PATH_OR_METADATA/);
    assert.ok(!readFileSync(join(root,NAME)).equals(Buffer.alloc(512,18)));
  }finally{rmSync(root,{recursive:true,force:true});}
});

test('receipt is candidate-bound and cryptographic Ed25519 proof uses ephemeral keys',()=>{
  const data=buildReceipt('1'.repeat(64),'2'.repeat(64),512,new Date('2026-11-19T06:00:00.000Z'));
  assert.equal(data.candidateSha,CANDIDATE);
  assert.equal(data.expectedCurrentRelease,PREVIOUS);
  assert.equal(data.schema,'kmj.independent-offsite.restore.v1');
  assert.equal(data.productionDatabaseUnchanged,true);
  assert.equal(data.networkIsolationVerified,true);
  const kp=generateKeyPairSync('ed25519');
  const privateKey=Buffer.from(kp.privateKey.export({format:'pem',type:'pkcs8'}));
  const pub=Buffer.from(kp.publicKey.export({format:'pem',type:'spki'}));
  const payload=Buffer.from(JSON.stringify(data));
  const signature=signVerifiedPayload(payload,privateKey,pub);
  assert.equal(signature.length,64);
  assert.equal(verify(null,payload,kp.publicKey,signature),true);
  assert.equal(verify(null,Buffer.concat([payload,Buffer.from('X')]),kp.publicKey,signature),false);
  const attacker=generateKeyPairSync('ed25519');
  assert.throws(()=>signVerifiedPayload(payload,privateKey,Buffer.from(attacker.publicKey.export({format:'pem',type:'spki'}))),/ED25519_PUBLIC_PRIVATE_MISMATCH/);
});

test('owner image input is necessary but never sufficient to admit remote host or pull image',()=>{
  assert.equal(parseArgv(['--inspect','--image-sha256',HEX64]),HEX64);
  assert.equal(parseArgv(['--inspect','--image-sha256','not-a-digest']),null);
  assert.equal(args(['--execute','--image-sha256',HEX64,'--encrypted-sha256','b'.repeat(64),'--source-local-sha256','c'.repeat(64),'--bytes','512','--ack-disposable-pg-storage-restore']).bytes,512);
  assert.equal(args(['--execute','--image-sha256',HEX64,'--encrypted-sha256','b'.repeat(64),'--source-local-sha256','c'.repeat(64),'--bytes','512']),null);
  const vol='kmj-p520-verify-'+'c'.repeat(32);
  const decrypt=decryptArgs(vol,HEX64,'C:\\private\\cipher.age','C:\\private\\agekey');
  const validate=validateArgs(vol,HEX64,'b'.repeat(64));
  const restore=pgStorageArgs(vol,HEX64,'b'.repeat(64));
  for(const line of [decrypt,validate,restore]){
    assert.ok(line.includes('--pull=never'));
    assert.ok(line.includes('--network=none'));
    assert.ok(line.includes('--read-only'));
    assert.ok(line.includes('--cap-drop=ALL'));
    assert.ok(!line.includes('--privileged'));
    assert.ok(line.includes('sha256:'+HEX64));
  }
  assert.ok(restore.includes('--user=postgres'));
  assert.ok(!validate.includes('--mount=type=bind,src=C:\\private\\agekey,dst=/identity.agekey,readonly'));
});

test('embedded Python bundle and nonroot restore code compile on Linux CI', {skip:process.platform==='win32'},()=>{
  const payload=JSON.stringify({a:VALIDATION_PY,b:RESTORE_PY});
  const p=spawnSync('python3',['-I','-B','-c',
    'import json,sys\nx=json.loads(sys.stdin.read())\nfor value in x.values():compile(value,"<generated>","exec")'],
    {encoding:'utf8',input:payload,timeout:15000});
  assert.equal(p.status,0,p.stdout+p.stderr);
});
