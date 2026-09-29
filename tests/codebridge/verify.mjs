import fs from 'node:fs';
import assert from 'node:assert/strict';
const {verifyEntitlement}=await import('../../.codebridge-contract/src/license.js');
const fixture=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const result=verifyEntitlement(fixture.token,fixture.keys,fixture.binding,fixture.now);
assert.equal(result.product,'KMJ_CODEBRIDGE');assert.equal(result.state,'ACTIVE');assert.equal(result.limits.concurrent_jobs,2);
assert.throws(()=>verifyEntitlement(fixture.token,fixture.keys,{...fixture.binding,device:'other'},fixture.now),/LICENSE_INVALID/);
assert.throws(()=>verifyEntitlement(fixture.token,fixture.keys,fixture.binding,fixture.now+300000),/LICENSE_INVALID/);
console.log('PHP to CodeBridge Node verification: 3 passed');
