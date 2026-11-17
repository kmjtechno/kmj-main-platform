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

const PY_EXTRACT_FIXTURE="import hashlib\nimport io\nfrom pathlib import Path\nimport sys\nimport tarfile\nimport tempfile\n\nSRC=sys.stdin.read()\nscope={\"__name__\":\"kmj_fixture\"}\nexec(compile(SRC,\"<isolated-p520-recovery>\",\"exec\"),scope)\nSOURCE=\"c\"*64\nCANDIDATE=\"4c9d59103b99a6cfe675bb7b8961fc956eb294f0\"\n\ndef bundle(name,archive):\n    db=b\"PGDMP\"+b\"synthetic_payload\"*5\n    middle=io.BytesIO()\n    data=b\"KMJ synthetic upload - NOT customer data\"\n    with tarfile.open(fileobj=middle,mode=\"w:gz\") as nested:\n        path=\"storage/app/sample.txt\"\n        if name==\"path_traversal\":path=\"../etc/passwd\"\n        if name==\"secret_env\":path=\"storage/app/.env.production\"\n        if name==\"mixed_case_secret_env\":path=\"storage/app/.ENV.local\"\n        if name==\"symlink\":path=\"storage/app/escape\"\n        ti=tarfile.TarInfo(path)\n        if name==\"symlink\":\n            ti.type=tarfile.SYMTYPE\n            ti.linkname=\"/etc/passwd\"\n            nested.addfile(ti)\n        else:\n            ti.size=len(data)\n            nested.addfile(ti,io.BytesIO(data))\n    storage=middle.getvalue()\n    meta=(\"backup_kind=offsite_sanitized_local_witness\\n\"\n      \"source_local_sha256=\"+SOURCE+\"\\n\"\n      \"target_sha=\"+(\"f\"*40 if name==\"wrong_candidate\" else CANDIDATE)+\"\\n\"\n      \"current_release=platform-ce6ad7dc9d89\\n\"\n      \"production_env_excluded=YES\\n\").encode(\"ascii\")\n    content={\"database.dump\":db,\"storage.tar.gz\":storage,\"metadata.txt\":meta}\n    sha={k:hashlib.sha256(v).hexdigest() for k,v in content.items()}\n    if name==\"wrong_dump_digest\":sha[\"database.dump\"]=\"0\"*64\n    manifest=\"\".join(sha[k]+\"  \"+k+\"\\n\" for k in content).encode(\"ascii\")\n    content[\"SHA256SUMS\"]=manifest\n    with tarfile.open(archive,\"w:gz\") as t:\n        for key,value in content.items():\n            ti=tarfile.TarInfo(key)\n            ti.size=len(value)\n            t.addfile(ti,io.BytesIO(value))\n    return data\n\nfor name in [\"valid\",\"path_traversal\",\"secret_env\",\"mixed_case_secret_env\",\"symlink\",\"wrong_candidate\",\"wrong_dump_digest\"]:\n    with tempfile.TemporaryDirectory(prefix=\"kmj-p520-source-qa-\") as tmp:\n        root=Path(tmp)\n        scope[\"DUMP\"]=root/\"dump\"\n        scope[\"STORAGE\"]=root/\"storage\"\n        archive=root/\"recovery.tgz\"\n        expected=bundle(name,archive)\n        try:\n            with tarfile.open(archive,\"r:gz\") as t:\n                members,manifest=scope[\"archive_check\"](t,SOURCE)\n                scope[\"copy_dump\"](t,members[\"database.dump\"],manifest[\"database.dump\"])\n                count=scope[\"copy_storage\"](t,members[\"storage.tar.gz\"],manifest[\"storage.tar.gz\"])\n            if name!=\"valid\":raise AssertionError(\"malformed archive accepted: \"+name)\n            if count!=1 or (root/\"storage\"/\"storage\"/\"app\"/\"sample.txt\").read_bytes()!=expected:\n                raise AssertionError(\"restored synthetic uploads parity wrong\")\n        except (ValueError, OSError, tarfile.TarError):\n            if name==\"valid\":raise\nprint(\"KMJ_P520_REAL_SYNTHETIC_EXTRACTION=PASS\")\n";

test('actual Python source copies/restores synthetic PGDMP/uploads and refuses malformed archives',()=>{
  const r=spawnSync('python3',['-c',PY_EXTRACT_FIXTURE],{
    input:RESTORE_PY,encoding:'utf8',timeout:20000,maxBuffer:32768
  });
  assert.equal(r.status,0,r.stderr);
  assert.equal(r.stdout.trim(),'KMJ_P520_REAL_SYNTHETIC_EXTRACTION=PASS');
});
