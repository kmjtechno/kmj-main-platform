#!/usr/bin/env node
// P520 only: sign a genuine completed, verified local networkless restore.
// Imported by the guarded restore runner AFTER all Docker phases and cleanup.
// No arbitrary user JSON, secrets in logs, Google dependency or release approval.
import { createHash,createPrivateKey,createPublicKey,sign,verify } from 'node:crypto';
import { constants,existsSync,fstatSync,lstatSync,openSync,readFileSync,closeSync,writeFileSync } from 'node:fs';
import { join } from 'node:path';
import os from 'node:os';
import { verifyWindowsPrivateAcl } from './P520-OFFSITE-ACL-VERIFY-20261116.mjs';
import { verifyWindowsPrivateChildFileAcl } from './P520-OFFSITE-FILE-ACL-READONLY-20261118.mjs';

const HEX=/^[0-9a-f]{64}$/;
const CANDIDATE='bd8975f0ee888a26013a6669e687db540f39f440';
const PREVIOUS='platform-ce6ad7dc9d89';

export function buildReceipt(cipherSha,sourceSha,bytes,when=new Date()){
  if(!HEX.test(cipherSha)||!HEX.test(sourceSha)||
     !Number.isSafeInteger(bytes)||bytes<256||bytes>10*1024**3||
     !(when instanceof Date)||!Number.isFinite(when.getTime()))throw Error('INVALID_EVIDENCE');
  return {
    schema:'kmj.independent-offsite.restore.v1',
    receiver:'p520',
    receiverHost:'DESKTOP-5FVJMET',
    candidateSha:CANDIDATE,
    expectedCurrentRelease:PREVIOUS,
    encryptedSha256:cipherSha,
    sourceLocalSha256:sourceSha,
    receivedCipherSha256:cipherSha,
    receivedCipherBytes:bytes,
    decryptVerified:true,
    bundleManifestVerified:true,
    isolatedPostgresRestoreVerified:true,
    restoredStorageParityVerified:true,
    networkIsolationVerified:true,
    productionDatabaseUnchanged:true,
    completedAtUtc:when.toISOString()
  };
}
export function signVerifiedPayload(payload,privatePem,publicPem){
  if(!Buffer.isBuffer(payload)||payload.length>16384||!payload.length||
     !Buffer.isBuffer(privatePem)||!Buffer.isBuffer(publicPem))throw Error('BAD_SIGNING_INPUT');
  const key=createPrivateKey(privatePem);
  const publicKey=createPublicKey(publicPem);
  const signature=sign(null,payload,key);
  if(signature.length!==64||!verify(null,payload,publicKey,signature))
    throw Error('ED25519_PUBLIC_PRIVATE_MISMATCH');
  return signature;
}
function readPrivateFile(path,max){
  // Fail closed before reading a private key if Windows owner/ACL has drifted.
  if(!verifyWindowsPrivateChildFileAcl(path))throw Error('PRIVATE_FILE_ACL_UNTRUSTED');
  const before=lstatSync(path,{bigint:true});
  if(!before.isFile()||before.isSymbolicLink()||before.nlink!==1n||
     before.size<32n||before.size>BigInt(max))throw Error('PRIVATE_FILE_METADATA');
  const fd=openSync(path,constants.O_RDONLY|(constants.O_NOFOLLOW||0));
  try{
    const after=fstatSync(fd,{bigint:true});
    if(after.dev!==before.dev||after.ino!==before.ino||
       after.nlink!==1n||after.size!==before.size||!after.isFile())
       throw Error('PRIVATE_FILE_CHANGED');
    const data=readFileSync(fd);
    if(BigInt(data.length)!==before.size)throw Error('PRIVATE_FILE_TRUNCATED');
    return data;
  }finally{closeSync(fd);}
}
export function signAfterRestore({parent,cipherSha,sourceSha,bytes}){
  if(process.platform!=='win32'||os.hostname().toUpperCase()!=='DESKTOP-5FVJMET')
    throw Error('WRONG_OWNER_HOST');
  if(!parent||!verifyWindowsPrivateAcl(parent))throw Error('PRIVATE_ACL_NOT_VERIFIED');
  const privatePem=readPrivateFile(join(parent,'p520-receipt-signing-ed25519.pem'),8192);
  const publicPem=readPrivateFile(join(parent,'p520-receipt-ed25519-public.pem'),4096);
  const receipt=buildReceipt(cipherSha,sourceSha,bytes);
  const raw=Buffer.from(JSON.stringify(receipt),'utf8');
  const signature=signVerifiedPayload(raw,privatePem,publicPem);
  const stamp=receipt.completedAtUtc.replace(/[-:.]/g,'');
  const label='p520-bd8975f0ee88-independent-restore-'+stamp;
  const receiptFile=join(parent,label+'.json');
  const signatureFile=join(parent,label+'.sig');
  if(existsSync(receiptFile)||existsSync(signatureFile))throw Error('RECEIPT_ALREADY_EXISTS');
  // No-clobber mode. If either write fails, preserve the partial evidence.
  // Never falsely claim a pair was published or overwrite any older record.
  writeFileSync(receiptFile,raw,{flag:'wx',mode:0o600});
  writeFileSync(signatureFile,signature,{flag:'wx',mode:0o600});
  return {
    receiptFile,
    signatureFile,
    publicKeySha256:createHash('sha256').update(publicPem).digest('hex'),
    bytes:raw.length
  };
}
