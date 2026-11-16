#!/usr/bin/env node
// KMJ P520 actual isolated AGE decrypt and key-free integrity only.
// No database/storage restoration and NO approval. Owner must run --execute.
import { randomUUID } from 'node:crypto';
import { lstatSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import os from 'node:os';
import { pathToFileURL } from 'node:url';
import { admission, ownerPinnedImage, safePath } from './P520-OFFSITE-CONTAINER-ADMISSION-20261116.mjs';
import { fixedRecoveryPath, verifyCipher } from './P520-OFFSITE-CIPHER-READBACK-20261116.mjs';
import { pgStorageArgs } from './P520-OFFSITE-PG-STORAGE-RESTORE-20261116.mjs';

const HEX=/^[a-f0-9]{64}$/;
const DOCKER='C:\\Program Files\\Docker\\Docker\\resources\\bin\\docker.exe';
const ENDPOINTS=new Set(['npipe:////./pipe/dockerDesktopLinuxEngine','npipe:////./pipe/docker_engine']);
const RECEIPT='KMJ_P520_BUNDLE_INTEGRITY=PASS';

export function args(argv) {
  if(argv.length!==10||argv[0]!=='--execute'||argv[1]!=='--image-sha256'||
     argv[3]!=='--encrypted-sha256'||argv[5]!=='--source-local-sha256'||
     argv[7]!=='--bytes'||argv[9]!=='--ack-bundle-only')return null;
  if(![argv[2],argv[4],argv[6]].every(x=>HEX.test(x))||
     !/^[1-9][0-9]{2,10}$/.test(argv[8])||Number(argv[8])>10*1024**3)return null;
  return {image:argv[2],cipher:argv[4],source:argv[6],bytes:Number(argv[8])};
}
export function localEndpoint(v){return ENDPOINTS.has(v?.trim());}
export function containerBase(volume){
  if(!/^kmj-p520-verify-[a-f0-9]{32}$/.test(volume))throw Error('VOLUME_NAME');
  return ['run','--rm','--pull=never','--network=none','--read-only',
    '--cap-drop=ALL','--security-opt=no-new-privileges',
    '--pids-limit=64','--memory=1024m','--cpus=1',
    '--tmpfs=/tmp:rw,noexec,nosuid,size=128m',
    '--mount=type=volume,src='+volume+',dst=/recovery'];
}
export function decryptArgs(volume,image,cipher,key){
  if(!HEX.test(image)||![cipher,key].every(safePath))throw Error('UNSAFE_INPUT');
  return [...containerBase(volume),
    '--mount=type=bind,src='+cipher+',dst=/sealed.age,readonly',
    '--mount=type=bind,src='+key+',dst=/identity.agekey,readonly',
    '--entrypoint=/bin/sh','sha256:'+image,
    '-ec','umask 077; age -d -i /identity.agekey -o /recovery/bundle.tar.gz /sealed.age; chmod 0644 /recovery/bundle.tar.gz'];
}
export const VALIDATION_PY="import hashlib, re, sys, tarfile\nfrom pathlib import PurePosixPath\nfrom io import BytesIO\nsource=sys.argv[1]\nexpected_names={\"database.dump\",\"storage.tar.gz\",\"metadata.txt\",\"SHA256SUMS\"}\nchecks={}\nbundle=sys.argv[2] if len(sys.argv)==3 else \"/recovery/bundle.tar.gz\"\nwith tarfile.open(bundle,\"r:gz\") as arc:\n    members=arc.getmembers()\n    if len(members)!=4 or {m.name for m in members}!=expected_names:\n        raise SystemExit(\"INVALID_OUTER_MEMBERS\")\n    if any(not m.isfile() or m.size<=0 for m in members):\n        raise SystemExit(\"NONREGULAR_MEMBER\")\n    if sum(m.size for m in members)>2*1024**3:\n        raise SystemExit(\"UNBOUNDED_ARCHIVE\")\n    if any(m.size>16384 for m in members if m.name in {\"metadata.txt\",\"SHA256SUMS\"}):\n        raise SystemExit(\"OVERSIZED_METADATA\")\n    small={}\n    for item in members:\n        stream=arc.extractfile(item)\n        if stream is None:raise SystemExit(\"UNREADABLE_MEMBER\")\n        digest=hashlib.sha256()\n        total=0\n        data=BytesIO() if item.name in {\"metadata.txt\",\"SHA256SUMS\"} else None\n        while True:\n            block=stream.read(1024*1024)\n            if not block:break\n            total+=len(block)\n            if total>item.size:raise SystemExit(\"MEMBER_GROWTH\")\n            if item.name==\"database.dump\" and total==len(block) and not block.startswith(b\"PGDMP\"):\n                raise SystemExit(\"NOT_PGDMP\")\n            digest.update(block)\n            if data is not None:data.write(block)\n        if total!=item.size:raise SystemExit(\"MEMBER_TRUNCATED\")\n        checks[item.name]=digest.hexdigest()\n        if data is not None:small[item.name]=data.getvalue().decode(\"ascii\")\n    manifest={}\n    for line in small[\"SHA256SUMS\"].splitlines():\n        m=re.fullmatch(r\"([a-f0-9]{64})  (database\\.dump|storage\\.tar\\.gz|metadata\\.txt)\",line)\n        if not m or m.group(2) in manifest:raise SystemExit(\"MANIFEST_INVALID\")\n        manifest[m.group(2)]=m.group(1)\n    if set(manifest)!=expected_names-{\"SHA256SUMS\"} or any(checks[k]!=digest for k,digest in manifest.items()):\n        raise SystemExit(\"MANIFEST_MISMATCH\")\n    meta={}\n    for line in small[\"metadata.txt\"].splitlines():\n        key,sep,value=line.partition(\"=\")\n        if not sep or key in meta:raise SystemExit(\"METADATA_INVALID\")\n        meta[key]=value\n    expected={\n        \"backup_kind\":\"offsite_sanitized_local_witness\",\n        \"source_local_sha256\":source,\n        \"target_sha\":\"4c9d59103b99a6cfe675bb7b8961fc956eb294f0\",\n        \"current_release\":\"platform-ce6ad7dc9d89\",\n        \"production_env_excluded\":\"YES\"}\n    if meta!=expected:raise SystemExit(\"METADATA_MISMATCH\")\n    # Validate nested storage before any extraction. No AGE key is mounted here.\n    nested=next(m for m in members if m.name==\"storage.tar.gz\")\n    nested_stream=arc.extractfile(nested)\n    if nested_stream is None:raise SystemExit(\"STORAGE_UNREADABLE\")\n    names=set()\n    entries=0\n    uncompressed=0\n    with tarfile.open(fileobj=nested_stream,mode=\"r|gz\") as storage:\n        for m in storage:\n            entries+=1\n            uncompressed+=m.size\n            p=PurePosixPath(m.name)\n            canonical=p.as_posix()\n            if (entries>100000 or m.size<0 or\n                uncompressed>256*1024**3 or canonical in names or\n                p.is_absolute() or \"..\" in p.parts or\n                p.parts[:2]!=(\"storage\",\"app\") or\n                not (m.isfile() or m.isdir()) or\n                m.sparse is not None or \"\\\\\" in m.name or\n                any(part.lower().startswith(\".env\") for part in p.parts)):\n                raise SystemExit(\"UNSAFE_STORAGE_ARCHIVE\")\n            names.add(canonical)\n    if entries==0:raise SystemExit(\"EMPTY_STORAGE_ARCHIVE\")\nprint(\"KMJ_P520_BUNDLE_INTEGRITY=PASS\")\n";
export function validateArgs(volume,image,source){
  if(!HEX.test(image)||!HEX.test(source))throw Error('INVALID_SHA');
  return [...containerBase(volume),'--entrypoint=python3','sha256:'+image,'-c',VALIDATION_PY,source];
}
function docker(args,timeout=900000) {
  const env={...process.env,DOCKER_CLI_HINTS:'false'};
  for(const k of ['DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH'])delete env[k];
  const r=spawnSync(DOCKER,args,{encoding:'utf8',timeout,maxBuffer:65536,windowsHide:true,env});
  if(r.error||r.status!==0||typeof r.stdout!=='string')throw Error('DOCKER_COMMAND_FAILED');
  return r.stdout.trim();
}
function fail(reason) {
  console.log('KMJ_P520_BUNDLE_ONLY=BLOCKED_'+(/^[A-Z0-9_]{1,80}$/.test(reason)?reason:'UNCLASSIFIED'));
  console.log('POSTGRESQL_RESTORE=NOT_EXECUTED');
  console.log('STORAGE_RESTORE=NOT_EXECUTED');
  console.log('PRODUCTION_APPROVAL=NOT_GRANTED');
  process.exitCode=2;
}
function execute(argv){
  const opt=args(argv);
  if(!opt)return fail('EXACT_ARGS');
  if(process.platform!=='win32'||os.hostname().toUpperCase()!=='DESKTOP-5FVJMET')return fail('WRONG_P520_HOST');
  if(!existsSync(DOCKER))return fail('PINNED_DOCKER_CLI_MISSING');
  let vol='',created=false,passed=false,cleaned=false,restoreStarted=false;
  try{
    const paths=fixedRecoveryPath(process.env.LOCALAPPDATA);
    const key=join(paths.parent,'p520-offsite.agekey');
    if(!safePath(key)||!safePath(paths.cipher))return fail('UNSAFE_PRIVATE_PATH');
    const gate=admission(opt.image,process.env.LOCALAPPDATA);
    if(!gate.ok)return fail('ADMISSION_'+gate.reason);
    const endpoint=docker(['context','inspect','--format','{{(index .Endpoints "docker").Host}}'],15000);
    if(!localEndpoint(endpoint))return fail('REMOTE_DOCKER_ENGINE');
    if(!ownerPinnedImage(join(paths.parent,'restore-image.sha256'),opt.image))return fail('OWNER_IMAGE_NOT_PINNED');
    const st=lstatSync(key);
    if(!st.isFile()||st.isSymbolicLink()||st.nlink!==1)return fail('KEY_FILE_UNSAFE');
    verifyCipher(paths.cipher,opt.cipher,opt.bytes);
    vol='kmj-p520-verify-'+randomUUID().replaceAll('-','');
    const createdName=docker(['volume','create','--name',vol],15000);
    if(createdName!==vol)throw Error('VOLUME_CREATE_NOT_EXACT');
    created=true;
    docker(decryptArgs(vol,opt.image,paths.cipher,key));
    const out=docker(validateArgs(vol,opt.image,opt.source));
    if(out!==RECEIPT)throw Error('BUNDLE_RECEIPT_INVALID');
    restoreStarted=true;
    const recovered=docker(pgStorageArgs(vol,opt.image,opt.source),900000);
    if(recovered!=='KMJ_P520_DISPOSABLE_PG_STORAGE=PASS')throw Error('DISPOSABLE_RESTORE_INVALID');
    passed=true;
  }catch{
    fail(restoreStarted?'DISPOSABLE_PG_STORAGE_RESTORE_FAILED':'DECRYPT_OR_INTEGRITY');
  }finally{
    if(created){
      try{docker(['volume','rm',vol],15000);cleaned=true;}
      catch{fail('PLAINTEXT_VOLUME_CLEANUP_FAILED');}
    }
  }
  if(passed&&cleaned&&process.exitCode!==2){
    console.log('KMJ_P520_BUNDLE_ONLY=PASS');
    console.log('KEY_SEPARATION_TWO_CONTAINERS=PASS');
    console.log('ENCRYPTED_SHA_AND_CANDIDATE_METADATA=PASS');
    console.log('POSTGRESQL_RESTORE=PASS_DISPOSABLE');
    console.log('STORAGE_RESTORE=PASS_DISPOSABLE');
    console.log('OWNER_SIGNED_INDEPENDENT_RECEIPT=REQUIRED');
    console.log('PRODUCTION_APPROVAL=NOT_GRANTED');
  }
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
  try{execute(process.argv.slice(2));}catch{fail('UNEXPECTED_SAFE_BLOCK');}
}
