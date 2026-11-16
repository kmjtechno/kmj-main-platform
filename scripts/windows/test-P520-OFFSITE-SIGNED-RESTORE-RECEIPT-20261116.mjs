import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash,generateKeyPairSync,sign} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {writeFileSync,mkdtempSync,rmSync} from 'node:fs';
import {join} from 'node:path';
import os from 'node:os';
import {buildReceipt,signVerifiedPayload,signAfterRestore} from './P520-OFFSITE-SIGNED-RESTORE-RECEIPT-20261116.mjs';

const A='a'.repeat(64),B='b'.repeat(64);
test('candidate/predecessor and all mandatory proof flags exactly match Elite verifier',()=>{
 const receipt=buildReceipt(A,B,441334,new Date('2026-11-16T15:01:00.000Z'));
 assert.equal(receipt.candidateSha,'4c9d59103b99a6cfe675bb7b8961fc956eb294f0');
 assert.equal(receipt.expectedCurrentRelease,'platform-ce6ad7dc9d89');
 assert.equal(receipt.receivedCipherSha256,A);
 assert.equal(receipt.productionDatabaseUnchanged,true);
 assert.equal(Object.keys(receipt).length,16);
 for(const [input,source,bytes] of [['NOT_SHA',B,441334],[A,'NOT_SHA',441334],
   [A,B,-1],[A,B,11*1024**3]]){
   assert.throws(()=>buildReceipt(input,source,bytes));
 }
});
test('ephemeral test key signs exact bytes; public key or payload mismatch rejected',()=>{
 const a=generateKeyPairSync('ed25519');
 const b=generateKeyPairSync('ed25519');
 const priv=Buffer.from(a.privateKey.export({format:'pem',type:'pkcs8'}));
 const pub=Buffer.from(a.publicKey.export({format:'pem',type:'spki'}));
 const wrongPub=Buffer.from(b.publicKey.export({format:'pem',type:'spki'}));
 const bytes=Buffer.from(JSON.stringify(buildReceipt(A,B,441334)));
 assert.equal(signVerifiedPayload(bytes,priv,pub).length,64);
 assert.throws(()=>signVerifiedPayload(bytes,priv,wrongPub),/ED25519_PUBLIC_PRIVATE_MISMATCH/);
 assert.throws(()=>signVerifiedPayload(Buffer.alloc(16385),priv,pub));
});
test('real Python/openssl Elite verifier accepts only synthetic signed fixture',()=>{
 const pair=generateKeyPairSync('ed25519');
 const priv=Buffer.from(pair.privateKey.export({format:'pem',type:'pkcs8'}));
 const pub=Buffer.from(pair.publicKey.export({format:'pem',type:'spki'}));
 const receipt=Buffer.from(JSON.stringify(buildReceipt(A,B,441334)));
 const sig=signVerifiedPayload(receipt,priv,pub);
 const temp=mkdtempSync(join(os.tmpdir(),'kmj-p520-cross-language-'));
 try {
  const payload=join(temp,'receipt.json'),signature=join(temp,'receipt.sig'),key=join(temp,'public.pem');
  writeFileSync(payload,receipt);
  writeFileSync(signature,sig);
  writeFileSync(key,pub);
  const script=[
   'import importlib.util,sys',
   'from pathlib import Path',
   'path=Path("scripts/operations/verify-p520-independent-restore-20261116.py")',
   'spec=importlib.util.spec_from_file_location("kmj_verifier",path)',
   'm=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)',
   'p,s,k,kh,enc,src=sys.argv[1:]',
   'r=m.verify(Path(p).read_bytes(),Path(s).read_bytes(),Path(k).read_bytes(),kh,enc,src)',
   'print(r["receiptCrypto"]+"_"+r["productionApproval"])'
  ].join('\n');
  const verified=spawnSync('python3',['-c',script,payload,signature,key,
   createHash('sha256').update(pub).digest('hex'),A,B],{encoding:'utf8',timeout:15000});
  assert.equal(verified.status,0,verified.stderr);
  assert.equal(verified.stdout.trim(),'PASS_NOT_GRANTED');
  writeFileSync(payload,Buffer.from(receipt.toString().replace('441334','441335')));
  const wrong=spawnSync('python3',['-c',script,payload,signature,key,
   createHash('sha256').update(pub).digest('hex'),A,B],{encoding:'utf8',timeout:15000});
  assert.notEqual(wrong.status,0);
 } finally {rmSync(temp,{recursive:true,force:true});}
});
test('real P520 key access cannot run from hosted Linux synthetic CI',()=>{
 if(process.platform!=='win32')assert.throws(()=>signAfterRestore({
  parent:'/tmp/unsafe',cipherSha:A,sourceSha:B,bytes:441334
 }),/WRONG_OWNER_HOST/);
});
