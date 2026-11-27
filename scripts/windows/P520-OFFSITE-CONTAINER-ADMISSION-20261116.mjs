#!/usr/bin/env node
// KMJ P520 container-only isolated PostgreSQL restore admission doctor.
// No Docker pulls, builds, containers, keys, archives, credentials or disk writes.
import { spawnSync } from 'node:child_process';
import { lstatSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import os from 'node:os';
import { pathToFileURL } from 'node:url';
import { fixedRecoveryPath } from './P520-OFFSITE-CIPHER-READBACK-20261116.mjs';
import { verifyWindowsPrivateAcl } from './P520-OFFSITE-ACL-VERIFY-20261116.mjs';

const HASH=/^[a-f0-9]{64}$/;
const FAIL='KMJ_P520_CONTAINER_ADMISSION=BLOCKED_';

export function parseArgv(args) {
  if (args.length!==3||args[0]!=='--inspect'||args[1]!=='--image-sha256'||!HASH.test(args[2])) {
    return null;
  }
  return args[2];
}
export function dockerInfo(output) {
  if(typeof output!=='string'||output.length>2048)return false;
  const lines=output.trim().split(/\r?\n/);
  return lines.length===1&&lines[0].trim()==='linux';
}
export function validateImageId(value, digest) {
  return HASH.test(digest)&&value?.trim()===('sha256:'+digest);
}
export function ownerPinnedImage(policyFile,imageSha) {
  if(!HASH.test(imageSha))return false;
  try {
    const st=lstatSync(policyFile);
    if(!st.isFile()||st.isSymbolicLink()||st.nlink!==1||
       st.size<64||st.size>66)return false;
    const contents=readFileSync(policyFile,{encoding:'ascii'});
    return contents===imageSha||contents===imageSha+'\n'||contents===imageSha+'\r\n';
  }catch{return false;}
}
export function safePath(value) {
  return typeof value==='string'&&value.length>0&&value.length<1024&&
    !/[\r\n\0,]/.test(value);
}
export function runReadonlyDocker(args) {
  const result=spawnSync('docker.exe',args,{encoding:'utf8',timeout:15000,maxBuffer:8192,windowsHide:true,
    env:{...process.env,DOCKER_CLI_HINTS:'false',DOCKER_CONTENT_TRUST:'1'}});
  if(result.error||result.status!==0||typeof result.stdout!=='string')return null;
  return result.stdout;
}
export function admission(imageSha,host){
  if(process.platform!=='win32'||os.hostname().toUpperCase()!=='DESKTOP-5FVJMET')
    return {ok:false,reason:'OWNER_P520_HOST'};
  if(!safePath(host)||!safePath(process.env.LOCALAPPDATA))return {ok:false,reason:'PRIVATE_PATH_INVALID'};
  try {
    const {parent,inbox,cipher}=fixedRecoveryPath(process.env.LOCALAPPDATA);
    const key=join(parent,'p520-offsite.agekey');
    for(const path of [parent,inbox,key,cipher]){
      const st=lstatSync(path);
      if(st.isSymbolicLink())return {ok:false,reason:'UNSAFE_PATH_SYMLINK'};
    }
    if(!lstatSync(key).isFile()||!lstatSync(cipher).isFile())
      return {ok:false,reason:'KEY_OR_CIPHER_NOT_REGULAR'};
    if(!verifyWindowsPrivateAcl(parent)||!verifyWindowsPrivateAcl(inbox))
      return {ok:false,reason:'PRIVATE_ACL'};
    // Owner-approved private immutable image digest. CLI input alone is NOT authority.
    if(!ownerPinnedImage(join(parent,'restore-image.sha256'),imageSha))
      return {ok:false,reason:'OWNER_IMAGE_POLICY_NOT_PINNED'};
  }catch{return {ok:false,reason:'P520_KEYS_OR_CIPHER_NOT_PROVISIONED'};}
  const info=runReadonlyDocker(['info','--format','{{.OSType}}']);
  if(!dockerInfo(info))return {ok:false,reason:'DOCKER_LINUX_ENGINE'};
  // An immutable local IMAGE ID, not a mutable tag, remote digest pull or latest.
  // Never ask Docker to fetch from registry; locally installed image only.
  const exact='sha256:'+imageSha;
  const id=runReadonlyDocker(['image','inspect','--format','{{.Id}}',exact]);
  if(!validateImageId(id,imageSha))return {ok:false,reason:'LOCAL_IMAGE_NOT_PINNED'};
  return {ok:true,image:exact};
}
function fail(reason) {
  console.log(FAIL+reason);
  console.log('P520_DECRYPT_OR_DATABASE_RESTORE=NOT_EXECUTED');
  console.log('PRODUCTION_APPROVAL=NOT_GRANTED');
  process.exitCode=2;
}
function main(args) {
  const digest=parseArgv(args);
  if(!digest)return fail('EXACT_IMMUTABLE_IMAGE_ARG');
  const result=admission(digest,process.env.LOCALAPPDATA);
  if(!result.ok)return fail(result.reason);
  console.log('KMJ_P520_CONTAINER_ADMISSION=PASS_READ_ONLY');
  console.log('LOCAL_IMAGE_ID='+result.image);
  console.log('DOCKER_NETWORK_ISOLATION=REQUIRED_FOR_FUTURE_RUN');
  console.log('DOCKER_AUTO_PULL=FORBIDDEN');
  console.log('GOOGLE_VPS_DEPENDENCY=NONE');
  console.log('P520_DECRYPT_OR_DATABASE_RESTORE=NOT_EXECUTED');
  console.log('PRODUCTION_APPROVAL=NOT_GRANTED');
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)main(process.argv.slice(2));
