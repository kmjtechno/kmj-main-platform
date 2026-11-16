import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {writeFileSync, mkdtempSync, symlinkSync, linkSync, rmSync} from 'node:fs';
import {join} from 'node:path';
import os from 'node:os';
import {parseArgv,dockerInfo,validateImageId,safePath,runReadonlyDocker,ownerPinnedImage} from './P520-OFFSITE-CONTAINER-ADMISSION-20261116.mjs';

const SHA='b'.repeat(64);
test('only immutable SHA256 local image identity accepted',()=>{
  assert.equal(parseArgv(['--inspect','--image-sha256',SHA]),SHA);
  for(const argv of [
    [],['--help'],['--inspect'],
    ['--inspect','--image-sha256','ubuntu:latest'],
    ['--inspect','--image-sha256','sha256:'+SHA],
    ['--inspect','--image-sha256','B'.repeat(64)],
    ['--inspect','--image-sha256',SHA,'--restore']])
    assert.equal(parseArgv(argv),null);
});
test('Docker Linux engine must be sole verified platform output',()=>{
  assert.equal(dockerInfo('linux\n'),true);
  for(const bad of ['',null,'windows','linux\nwindows',' Linux junk','linux\nwarning'])
    assert.equal(dockerInfo(bad),false);
});
test('pin by local SHA256 image ID, not tags or remote registry refs',()=>{
  assert.equal(validateImageId('sha256:'+SHA+'\n',SHA),true);
  for(const bad of ['postgres:16','docker.io/postgres@sha256:'+SHA,'sha256:'+'c'.repeat(64),'',null])
    assert.equal(validateImageId(bad,SHA),false);
});
test('no comma/newline unsafe bind arguments',()=>{
  for(const bad of ['','C:\\Users\\bad,name','C:\\foo\nbar','C:\\foo\rbar','\0'])
    assert.equal(safePath(bad),false);
  assert.equal(safePath('C:\\Users\\KMJ TECHNO\\recovery'),true);
});
test('untrusted host rejects before invoking Docker',()=>{
  const s=spawnSync(process.execPath,['scripts/windows/P520-OFFSITE-CONTAINER-ADMISSION-20261116.mjs','--inspect','--image-sha256',SHA],
    {encoding:'utf8',timeout:10000});
  if(process.platform!=='win32'){
    assert.equal(s.status,2);
    assert.match(s.stdout,/BLOCKED_OWNER_P520_HOST/);
    assert.match(s.stdout,/NOT_EXECUTED/);
  }
});
test('source contract does not launch Docker container or pull image',()=>{
  const s=runReadonlyDocker.toString();
  assert.ok(s.includes('spawnSync'));
  assert.ok(!s.includes('docker pull'));
  assert.ok(!s.includes('docker run'));
});

test('owner-private local image policy must exactly pin SHA, not CLI only',()=>{
  const tmp=mkdtempSync(join(os.tmpdir(),'kmj-p520-docker-policy-'));
  try {
    const policy=join(tmp,'restore-image.sha256');
    writeFileSync(policy,SHA+'\n');
    assert.equal(ownerPinnedImage(policy,SHA),true);
    assert.equal(ownerPinnedImage(policy,'a'.repeat(64)),false);
    writeFileSync(policy,SHA+'\nsha256:latest\n');
    assert.equal(ownerPinnedImage(policy,SHA),false);
    writeFileSync(policy,SHA+'\n');
    const duplicate=join(tmp,'duplicate');
    linkSync(policy,duplicate);
    assert.equal(ownerPinnedImage(policy,SHA),false);
    rmSync(duplicate);
    rmSync(policy);
    symlinkSync(join(tmp,'untrusted'),policy);
    assert.equal(ownerPinnedImage(policy,SHA),false);
  } finally {
    rmSync(tmp,{recursive:true,force:true});
  }
});
