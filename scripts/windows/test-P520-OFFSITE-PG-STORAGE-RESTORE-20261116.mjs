import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {pgStorageArgs,RESTORE_PY} from './P520-OFFSITE-PG-STORAGE-RESTORE-20261116.mjs';
const sha='a'.repeat(64),volume='kmj-p520-verify-'+'b'.repeat(32);
test('untrusted image/volume or source digest not accepted',()=>{
 for(const [vol,img,src] of [
   ['other',sha,sha],[volume,'latest',sha],[volume,sha,'INVALID'],
   [volume,'sha256:'+sha,sha]])
   assert.throws(()=>pgStorageArgs(vol,img,src));
});
test('key-free Docker restore: no network, nonroot, no host or key bind',()=>{
 const x=pgStorageArgs(volume,sha,sha).join(' ');
 for(const need of ['--rm','--pull=never','--network=none','--read-only',
   '--cap-drop=ALL','--security-opt=no-new-privileges','--user=postgres',
   'dst=/recovery,readonly','--tmpfs=/tmp:','--memory=2048m',
   '--entrypoint=python3','sha256:'+sha])
   assert.ok(x.includes(need),need);
 for(const bad of ['identity.agekey','/sealed.age','--privileged','--network=host',
   '/var/run/docker.sock','--publish','--env-file'])
   assert.ok(!x.includes(bad),bad);
});
test('PG restore calls real initdb, pg_ctl, pg_restore and table query via UNIX socket',()=>{
 for(const x of ['os.geteuid()==0','KMJ_P520_NETWORKLESS',
   'initdb','pg_ctl','pg_restore','--single-transaction',
   '--exit-on-error','--no-owner','--no-privileges',
   "listen_addresses = ''",'unix_socket_directories',
   'pg_catalog.pg_class','NO_RESTORED_TABLES'])
   assert.ok(RESTORE_PY.includes(x),x);
});
test('uploads restore constrains traversal, symlinks and .env* and checks parity',()=>{
 for(const x of ['PurePosixPath','entry.sparse','..','storage','app','.env.',
   'STORAGE_RESTORED_PARITY','MAX_STORAGE','MAX_FILES','open(dest,"xb")'])
   assert.ok(RESTORE_PY.includes(x),x);
});
test('Python source parses and cannot restore without private volume/digest',()=>{
 const ast=spawnSync('python3',['-c','import ast,sys;ast.parse(sys.stdin.read())'],
   {input:RESTORE_PY,encoding:'utf8',timeout:10000});
 assert.equal(ast.status,0,ast.stderr);
 const p=spawnSync('python3',['-c',RESTORE_PY],
   {encoding:'utf8',timeout:10000});
 assert.notEqual(p.status,0);
 assert.ok(!p.stdout.includes('KMJ_P520_DISPOSABLE_PG_STORAGE=PASS'));
});
