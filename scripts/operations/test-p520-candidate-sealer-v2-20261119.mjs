import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';

const src='scripts/operations/seal-main-platform-p520-candidate-v2-20261119.py';
const body=readFileSync(src,'utf8');
const recipient='age1jgk7wrgccyu8s7wlh6zpxnm4qdvfus0d5t092s9zkjjmtwe8efjstvcs5u';
const pubKey=readFileSync('scripts/operations/p520-owner-observed-public-key-20261118.txt');
const sha='6216f2bc0bd7b63bea2f15bc771494fa6e2ab2fcfca01e75761a113120be81c4';

test('v2 sealer fixes immutable CE6->Licensing Hub identity, never old 4C9',()=>{
  assert.match(body,/EXACT_CANDIDATE = "bd8975f0ee888a26013a6669e687db540f39f440"/);
  assert.match(body,/EXACT_LIVE = "platform-ce6ad7dc9d89"/);
  assert.match(body,/if target.sha != EXACT_CANDIDATE or target.release != EXACT_LIVE:/);
  assert.match(body,/EXACT_CE6_TO_LICENSING_HUB_CANDIDATE_REQUIRED/);
  assert.doesNotMatch(body,/4c9d59103b99a6cfe675bb7b8961fc956eb294f0|EXACT_CE6_TO_4C9_REQUIRED/);
});
test('exact AGE recipient and exact Ed25519 SPKI PEM fingerprint pinned to Elite trust',()=>{
  assert.equal(createHash('sha256').update(pubKey).digest('hex'),sha);
  assert.match(body,/P520_RECIPIENT_PATH = Path\("\/etc\/kmj-p520-restore-trust\/p520-age-recipient.txt"\)/);
  assert.match(body,/P520_SIGNING_PUBLIC_PEM = Path\("\/etc\/kmj-p520-restore-trust\/p520-receipt-ed25519-public.pem"\)/);
  assert.ok(body.includes('OWNER_AGE_RECIPIENT = "'+recipient+'"'));
  assert.ok(body.includes('OWNER_PUBLIC_PEM_SHA256 = "'+sha+'"'));
  for(const marker of [
    'OWNER_PUBLIC_TRUST_DIRECTORY_UNSAFE','OWNER_ED25519_PUBLIC_PEM_METADATA',
    'OWNER_ED25519_PUBLIC_PEM_DIGEST','OWNER_AGE_RECIPIENT_NOT_PINNED',
    'recipient = verified_elite_public_pins()'
  ]) assert.ok(body.includes(marker),marker);
});
test('witness identity, no-clobber, env sanitization and release lock remain fail-closed',()=>{
  for(const marker of [
    'source_local_sha256=','production_env_excluded=YES',
    'ENV_EXCLUDED_FROM_OFFSITE_COPY=PASS','CURRENT.is_symlink()',
    'CURRENT.resolve(strict=True)','WITNESS_RELEASE_MISMATCH',
    'WITNESS_DIGEST_MISMATCH','ENCRYPTED_OUTPUT_EXISTS',
    'PRODUCTION_RELEASE=UNCHANGED','PRODUCTION_DB=UNTOUCHED'
  ]) assert.ok(body.includes(marker),marker);
  assert.match(body,/os\.link\(sealed, OUTPUT\)/);
  assert.match(body,/if name == "\.env":/);
  assert.match(body,/fcntl\.flock\(lock, fcntl\.LOCK_EX \| fcntl\.LOCK_NB\)/);
  assert.doesNotMatch(body,/subprocess\.run\(\s*\["(?:systemctl|ssh|scp|rsync|pg_restore)|git reset|git clean/);
});
test('Python source compiles and wrong candidate fails before host operation on Linux',{
  skip:process.platform==='win32'
},()=>{
  const code=[
    'import importlib.util,pathlib',
    "p=pathlib.Path('scripts/operations/seal-main-platform-p520-candidate-v2-20261119.py')",
    'compile(p.read_text(),str(p),"exec")',
    "spec=importlib.util.spec_from_file_location('kmj_candidate_sealer',p)",
    'm=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)',
    "assert m.Target(m.EXACT_CANDIDATE,m.EXACT_LIVE).short=='bd8975f0ee88'",
    'for wrong in (("4c9d59103b99a6cfe675bb7b8961fc956eb294f0",m.EXACT_LIVE),(m.EXACT_CANDIDATE,"platform-e5b43872bc03")):',
    " try:m.main(['--candidate-sha',wrong[0],'--expected-release',wrong[1]])",
    " except RuntimeError as e:assert str(e)=='EXACT_CE6_TO_LICENSING_HUB_CANDIDATE_REQUIRED'",
    " else:raise AssertionError('UNAUTHORIZED_CANDIDATE_ACCEPTED')"
  ].join('\n');
  const p=spawnSync('python3',['-I','-B','-c',code],{encoding:'utf8',timeout:15000});
  assert.equal(p.status,0,p.stdout+p.stderr);
});
