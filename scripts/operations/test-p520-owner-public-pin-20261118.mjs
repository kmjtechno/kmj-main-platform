import assert from 'node:assert/strict';
import test from 'node:test';
import { createHash, createPublicKey } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';

const prefix='scripts/operations/p520-owner-observed-';
const policy=JSON.parse(readFileSync(prefix+'public-identity-20261118.json','utf8'));
const pem=readFileSync(prefix+'public-key-20261118.pem');
const installerPath='scripts/operations/kmj-p520-owner-public-pin-20261118.sh';
const source=readFileSync(installerPath,'utf8');

test('P520 owner-reported public Ed25519 identity is exact pinned PEM; not release authority',()=>{
 assert.equal(policy.schema,'kmj.p520.observed-public-identity.v1');
 assert.equal(policy.receiver,'p520');
 assert.equal(policy.receiverHost,'DESKTOP-5FVJMET');
 assert.equal(policy.ageRecipient,'age1jgk7wrgccyu8s7wlh6zpxnm4qdvfus0d5t092s9zkjjmtwe8efjstvcs5u');
 assert.equal(policy.signingPublicPemSha256,'6216f2bc0bd7b63bea2f15bc771494fa6e2ab2fcfca01e75761a113120be81c4');
 assert.equal(createHash('sha256').update(pem).digest('hex'),policy.signingPublicPemSha256);
 const publicKey=createPublicKey(pem);
 assert.equal(publicKey.asymmetricKeyType,'ed25519');
 for(const key of ['eliteHostPinVerified','candidateSpecificEncryptedBackupVerified','independentPostgresStorageRestoreVerified','productionReleaseApprovalGranted']){
   assert.equal(policy[key],false,key);
 }
});

test('Installer embeds exact public pin, has no override, and cannot grant production approval',()=>{
 assert.ok(source.includes(policy.signingPublicPemSha256));
 assert.ok(source.includes(policy.ageRecipient));
 assert.ok(source.includes(pem.toString('base64')));
 for(const required of [
  'KMJ-elite', "mode=\"$1\"", '--inspect', '--apply',
  'root=', '0:0:700', '0:0:600:1', 'ln --', 'cmp -s --',
  'PRIVATE_TRUST_DIR_ACL', 'EXISTING_PUBLIC_KEY_CONFLICT',
  'PRODUCTION_APPROVAL=NOT_GRANTED', 'P520_CANDIDATE_BACKUP_RESTORE=NOT_EXECUTED'
 ])assert.ok(source.includes(required),required);
 assert.doesNotMatch(source,/curl|wget|ssh|sftp|age -d|pg_restore|systemctl|rm -rf|\/grant|\/reset|\/inheritance|sudo\s+.*\s+sh|eval\s/i);
});

test('Bash parser passes and wrong host is blocked before creating anything',()=>{
 const syntax=spawnSync('bash',['-n',installerPath],{encoding:'utf8',timeout:12000});
 assert.equal(syntax.status,0,syntax.stderr);
 const inspect=spawnSync('bash',[installerPath,'--inspect'],{encoding:'utf8',timeout:12000});
 assert.equal(inspect.status,2,inspect.stdout+inspect.stderr);
 assert.match(inspect.stdout,/KMJ_P520_PUBLIC_PIN=BLOCKED_OWNER_ELITE_ROOT_REQUIRED/);
 const apply=spawnSync('bash',[installerPath,'--apply'],{encoding:'utf8',timeout:12000});
 assert.equal(apply.status,2,apply.stdout+apply.stderr);
 assert.match(apply.stdout,/KMJ_P520_PUBLIC_PIN=BLOCKED_OWNER_ELITE_ROOT_REQUIRED/);
 assert.doesNotMatch(apply.stdout,/ELITE_PUBLIC_KEYS_OWNER_PIN=PASS/);
});
