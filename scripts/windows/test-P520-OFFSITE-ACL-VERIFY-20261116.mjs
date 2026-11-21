import test from 'node:test';
import assert from 'node:assert/strict';
import {trustedAclReport,verifyWindowsPrivateAcl} from './P520-OFFSITE-ACL-VERIFY-20261116.mjs';
const user='S-1-5-21-11111-22222-33333-1001';
function evidence(){return {Protected:true,OwnerSid:user,UserSid:user,Rules:[
 {Sid:user,Type:'Allow',Inherited:false,FullControl:true},
 {Sid:'S-1-5-18',Type:'Allow',Inherited:false,FullControl:true},
 {Sid:'S-1-5-32-544',Type:'Allow',Inherited:false,FullControl:true}]};}
test('explicit protected SID owner/SYSTEM/admin with full control allowed',()=>{
 assert.equal(trustedAclReport(evidence()),true);
});
test('foreign, inherited, privilege downgrade and access denial refused',()=>{
 const changes=[
 e=>{e.Protected=false},e=>{e.OwnerSid='S-1-5-18'},
 e=>{e.UserSid='S-1-5-32-544'},e=>{e.Rules[0].Inherited=true},
 e=>{e.Rules[0].FullControl=false},e=>{e.Rules[1].Type='Deny'},
 e=>{e.Rules.push({Sid:'S-1-1-0',Type:'Allow',Inherited:false,FullControl:true})},
 e=>{e.Rules.push({Sid:'S-1-5-11',Type:'Allow',Inherited:false,FullControl:true})},
 e=>{e.Rules.push({Sid:'S-1-5-32-545',Type:'Allow',Inherited:false,FullControl:true})},
 e=>{e.Rules.push({Sid:'S-1-5-21-11111-22222-33333-1002',Type:'Allow',Inherited:false,FullControl:true})}
 ];
 for(const change of changes){const e=evidence();change(e);assert.equal(trustedAclReport(e),false);}
});
test('missing malformed and oversized ACL evidence refused',()=>{
 for(const e of [null,{},[],{...evidence(),Rules:[]},
 {...evidence(),Rules:Array.from({length:13},()=>evidence().Rules[0])},
 {...evidence(),Rules:'not rules'}, {...evidence(),OwnerSid:'Everyone'}]){
   assert.equal(trustedAclReport(e),false);
 }
});
test('on Linux offline tests, no Windows ACL query runs',()=>{
 if(process.platform!=='win32')assert.equal(verifyWindowsPrivateAcl('/tmp/none'),false);
});
