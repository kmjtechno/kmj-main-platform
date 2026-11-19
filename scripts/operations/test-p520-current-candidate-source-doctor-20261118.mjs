import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';

const src='scripts/operations/kmj-p520-current-candidate-source-doctor-20261118.sh';
const body=readFileSync(src,'utf8');

test('CE6 production pointer and new draft Licensing Hub SHA are distinct and fixed',()=>{
  for(const exact of [
    'platform-ce6ad7dc9d89','bd8975f0ee888a26013a6669e687db540f39f440',
    'bd8975f0ee88','P520_DRAFT_SHA_OWNER_RELEASE_APPROVAL=NOT_GRANTED',
    'P520_PRODUCTION_PROTECTED_PREDECESSOR_MATCH=BLOCKED_E5B_VS_CE6'
  ])assert.ok(body.includes(exact),exact);
  assert.ok(!body.includes('4c9d59103b99a6cfe675bb7b8961fc956eb294f0'));
});
test('read-only preflight checks owner trust public recipient, local candidate exact backup witness and no release',()=>{
  for(const exact of [
    '/etc/kmj-p520-restore-trust','p520-receipt-ed25519-public.pem',
    'p520-age-recipient.txt',
    '6216f2bc0bd7b63bea2f15bc771494fa6e2ab2fcfca01e75761a113120be81c4',
    'age1jgk7wrgccyu8s7wlh6zpxnm4qdvfus0d5t092s9zkjjmtwe8efjstvcs5u',
    'pre-deploy-$CANDIDATE_SHORT.tar.gz','pre-deploy-$CANDIDATE_SHORT.json',
    'P520_CANDIDATE_LOCAL_WITNESS=PASS_BYTES_IDENTITY_ONLY',
    'P520_NEW_P520_ENCRYPTION_TRANSFER_RESTORE=NOT_VERIFIED',
    'P520_PRODUCTION_OR_BACKUP_MUTATION=NONE','PRODUCTION_APPROVAL=NOT_GRANTED'
  ])assert.ok(body.includes(exact),exact);
  assert.doesNotMatch(body,/\bcurl\b|\bwget\b|\bscp\b|\bsftp\b|\bssh\b|\bdocker\b|git\s+reset|git\s+clean|\b(?:systemctl|pg_restore|age -r|age -d)\b|\brm -rf\b|\bchmod\b|\bchown\b/);
  assert.doesNotMatch(body,/--prepare|--apply|--execute|--deploy/);
});
test('portable Bash parsing and wrong-host fail-closed --inspect and --prepare',()=>{
 const parsed=spawnSync('bash',['-n',src],{encoding:'utf8',timeout:12000});
 assert.equal(parsed.status,0,parsed.stdout+parsed.stderr);
 for(const argv of [[],['--inspect'],['--prepare']]){
  const r=spawnSync('bash',[src,...argv],{encoding:'utf8',timeout:12000});
  assert.equal(r.status,2,r.stdout+r.stderr);
  assert.match(r.stdout,/KMJ_P520_V2_SOURCE_DOCTOR=BLOCKED_(?:EXACT_READONLY_MODE|OWNER_ELITE_ROOT_REQUIRED)/);
  assert.doesNotMatch(r.stdout,/P520_CANDIDATE_LOCAL_WITNESS=PASS_BYTES_IDENTITY_ONLY/);
 }
});
