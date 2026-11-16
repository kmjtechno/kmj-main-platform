import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {args,localEndpoint,containerBase,decryptArgs,validateArgs,VALIDATION_PY} from './P520-OFFSITE-BUNDLE-ISOLATION-20261116.mjs';
const a='a'.repeat(64),b='b'.repeat(64),c='c'.repeat(64),vol='kmj-p520-verify-'+'d'.repeat(32);
const valid=['--execute','--image-sha256',a,'--encrypted-sha256',b,'--source-local-sha256',c,'--bytes','441334','--ack-bundle-only'];
test('only bounded exact digests and explicit non-production consent',()=>{
 assert.deepEqual(args(valid),{image:a,cipher:b,source:c,bytes:441334});
 for(const bad of [[],['--help'],valid.slice(0,9),
   valid.map((v,i)=>i===4?'INVALID':v),
   valid.map((v,i)=>i===8?'0':v),
   valid.map((v,i)=>i===9?'--deploy':v)])assert.equal(args(bad),null);
});
test('only local Docker Desktop named-pipe endpoints',()=>{
 assert.equal(localEndpoint('npipe:////./pipe/dockerDesktopLinuxEngine'),true);
 assert.equal(localEndpoint('npipe:////./pipe/docker_engine'),true);
 for(const value of [null,'ssh://google-vps1','tcp://127.0.0.1:2375','unix:///var/run/docker.sock'])
   assert.equal(localEndpoint(value),false);
});
test('decryption phase always isolated, key/cipher read-only',()=>{
 const cmd=decryptArgs(vol,a,'C:\\KMJ\\cipher.age','C:\\KMJ\\key.agekey').join(' ');
 for(const need of ['--pull=never','--network=none','--read-only','--cap-drop=ALL',
   '--security-opt=no-new-privileges','dst=/sealed.age,readonly',
   'dst=/identity.agekey,readonly','age -d -i /identity.agekey'])
   assert.ok(cmd.includes(need),need);
 for(const bad of ['--privileged','--network=host','--publish','/var/run/docker.sock'])
   assert.ok(!cmd.includes(bad));
});
test('independent verifier container has no AGE key or ciphertext bind',()=>{
 const cmd=validateArgs(vol,a,c).join(' ');
 assert.ok(cmd.includes('sha256:'+a));
 assert.ok(cmd.includes('--entrypoint=python3'));
 assert.ok(cmd.includes('--network=none'));
 assert.ok(!cmd.includes('identity.agekey'));
 assert.ok(!cmd.includes('sealed.age'));
 assert.ok(cmd.includes('production_env_excluded'));
});
test('strict bundle shape, manifest, no PG restore or release grant',()=>{
 for(const x of ['database.dump','storage.tar.gz','metadata.txt','SHA256SUMS',
   'PGDMP','source_local_sha256','production_env_excluded',
   'KMJ_P520_BUNDLE_INTEGRITY=PASS'])
   assert.ok(VALIDATION_PY.includes(x),x);
 assert.ok(!VALIDATION_PY.includes('pg_restore'));
});
test('Linux unit tests cannot run actual owner P520 restore',()=>{
 const p=spawnSync(process.execPath,['scripts/windows/P520-OFFSITE-BUNDLE-ISOLATION-20261116.mjs',...valid],
  {encoding:'utf8',timeout:10000});
 if(process.platform!=='win32'){
  assert.equal(p.status,2);
  assert.match(p.stdout,/BLOCKED_WRONG_P520_HOST/);
  assert.match(p.stdout,/POSTGRESQL_RESTORE=NOT_EXECUTED/);
 }
});
