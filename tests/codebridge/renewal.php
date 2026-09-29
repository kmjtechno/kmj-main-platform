<?php

declare(strict_types=1);

require __DIR__.'/encoder.php';
require __DIR__.'/../../apps/platform/app/Services/Licensing/CodeBridge/CodeBridgeRenewalService.php';

use App\Services\Licensing\CodeBridge\CodeBridgeRenewalService;
use App\Services\Licensing\Kslp\KslpSigner;

function database(int $now): PDO {
    $db = new PDO('sqlite::memory:', null, null, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
    $db->exec('CREATE TABLE codebridge_device_credentials (id TEXT PRIMARY KEY, license_id TEXT, activation_id TEXT, tenant_id TEXT, device_id TEXT, server_identity TEXT, token_hash TEXT UNIQUE, lease_sequence INTEGER, expires_at_epoch INTEGER, revoked_at TEXT)');
    $db->exec('CREATE TABLE kslp_licenses (id TEXT PRIMARY KEY, customer_id TEXT, product TEXT, plan TEXT, status TEXT, starts_at TEXT, expires_at TEXT, grace_until TEXT, revoked_at TEXT)');
    $db->exec('CREATE TABLE kslp_activations (id TEXT PRIMARY KEY, license_id TEXT, server_identity TEXT, deactivated_at TEXT)');
    $db->exec('CREATE TABLE plans (code TEXT UNIQUE, features TEXT, limits TEXT, status TEXT)');
    $db->exec('CREATE TABLE kslp_license_events (id INTEGER PRIMARY KEY AUTOINCREMENT, license_id TEXT, actor_id TEXT, action TEXT, reason TEXT, correlation_id TEXT, metadata TEXT, created_at TEXT)');
    $q=$db->prepare('INSERT INTO codebridge_device_credentials VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)');
    $q->execute(['credential-1','license-1','activation-1','customer-1','device-1','ed25519:registered',hash('sha256',str_repeat('a',48)),0,$now+300000,null]);
    $q=$db->prepare('INSERT INTO kslp_licenses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)');
    $q->execute(['license-1','customer-1','KMJ_CODEBRIDGE','professional','active',gmdate('Y-m-d H:i:s',$now-100),gmdate('Y-m-d H:i:s',$now+90000),gmdate('Y-m-d H:i:s',$now+200000),null]);
    $db->exec("INSERT INTO kslp_activations VALUES ('activation-1','license-1','ed25519:registered',NULL)");
    $q=$db->prepare('INSERT INTO plans VALUES (?, ?, ?, ?)');$q->execute(['codebridge.professional','{"read":true,"write":false,"execute":true}','{"devices":2,"concurrent_jobs":2}','active']);
    return $db;
}
function check(bool $condition): void {if(!$condition){throw new RuntimeException('Assertion failed');}}
function decode(string $token): array {return json_decode(base64_decode(strtr(explode('.',$token)[1],'-_','+/')),true,32,JSON_THROW_ON_ERROR);}
$request=['product'=>'KMJ_CODEBRIDGE','tenant'=>'customer-1','device'=>'device-1','sequence'=>0];
$db=database($now);$service=new CodeBridgeRenewalService($db,$signer);
$validToken=$service->renew(str_repeat('a',48),$request,$now);
$first=decode($validToken);
$second=decode($service->renew(str_repeat('a',48),$request,$now));
check($first['sequence']===1 && $second['sequence']===2);
check($first['features']===['read','execute']);check($first['exp']===$now+86400);check($first['grace_until']===$now+200000);
check((int)$db->query('SELECT COUNT(*) FROM kslp_license_events')->fetchColumn()===2);
$count=5;
foreach (["UPDATE kslp_licenses SET product='KMJ_CLOUDOS'", "UPDATE kslp_licenses SET customer_id='other'", "UPDATE kslp_licenses SET status='suspended'", "UPDATE kslp_licenses SET revoked_at='2026-01-01'", "UPDATE kslp_licenses SET expires_at='2000-01-01'", "UPDATE kslp_licenses SET starts_at='2099-01-01'", "UPDATE kslp_activations SET deactivated_at='2026-01-01'", "UPDATE kslp_activations SET server_identity='different'", "UPDATE codebridge_device_credentials SET revoked_at='2026-01-01'", "UPDATE codebridge_device_credentials SET expires_at_epoch=1", "UPDATE plans SET status='inactive'", "UPDATE plans SET limits='{\"devices\":0,\"concurrent_jobs\":1}'", "UPDATE plans SET features='{\"admin\":true}'"] as $sql) {
    $db=database($now);$db->exec($sql);$service=new CodeBridgeRenewalService($db,$signer);
    try {$service->renew(str_repeat('a',48),$request,$now);throw new RuntimeException('Expected denial');}catch(DomainException){}
    check((int)$db->query('SELECT lease_sequence FROM codebridge_device_credentials')->fetchColumn()===0);
    check((int)$db->query('SELECT COUNT(*) FROM kslp_license_events')->fetchColumn()===0);$count++;
}
foreach ([['tenant'=>'other'],['device'=>'other'],['sequence'=>999],['product'=>'KMJ_CLOUDOS']] as $change){
 $db=database($now);try{(new CodeBridgeRenewalService($db,$signer))->renew(str_repeat('a',48),array_replace($request,$change),$now);throw new RuntimeException('Expected denial');}catch(DomainException){}$count++;
}
$db=database($now);try{(new CodeBridgeRenewalService($db,$signer))->renew(str_repeat('b',48),$request,$now);throw new RuntimeException('Expected credential denial');}catch(DomainException){}$count++;
$db=database($now);$db->exec('DROP TABLE kslp_license_events');
try{(new CodeBridgeRenewalService($db,$signer))->renew(str_repeat('a',48),$request,$now);throw new RuntimeException('Expected audit failure');}catch(PDOException){}
check((int)$db->query('SELECT lease_sequence FROM codebridge_device_credentials')->fetchColumn()===0);$count++;
$db=database($now);$failedSigner=new class implements KslpSigner {public function kid():string{return 'failed';}public function sign(string $message):string{throw new RuntimeException('Signer offline');}};
try{(new CodeBridgeRenewalService($db,$failedSigner))->renew(str_repeat('a',48),$request,$now);throw new RuntimeException('Expected signer failure');}catch(RuntimeException $error){check($error->getMessage()==='Signer offline');}
check((int)$db->query('SELECT lease_sequence FROM codebridge_device_credentials')->fetchColumn()===0);$count++;
// A deactivated device must not consume the replacement device's slot.
$db=database($now);
$db->exec("UPDATE plans SET limits='{\"devices\":1,\"concurrent_jobs\":2}'");
$db->exec("INSERT INTO kslp_activations VALUES ('activation-old','license-1','ed25519:old','2026-01-01')");
$q=$db->prepare('INSERT INTO codebridge_device_credentials VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)');
$q->execute(['credential-old','license-1','activation-old','customer-1','device-old','ed25519:old',hash('sha256',str_repeat('c',48)),0,$now+300000,null]);
check(decode((new CodeBridgeRenewalService($db,$signer))->renew(str_repeat('a',48),$request,$now))['sequence']===1);$count++;
$db->exec("UPDATE kslp_activations SET deactivated_at=NULL WHERE id='activation-old'");
try{(new CodeBridgeRenewalService($db,$signer))->renew(str_repeat('a',48),$request,$now);throw new RuntimeException('Expected active device limit denial');}catch(DomainException){}$count++;
// Revocation propagation: once either the device credential or license is revoked, no later lease may be issued.
$db=database($now); $service=new CodeBridgeRenewalService($db,$signer);
check(decode($service->renew(str_repeat('a',48),$request,$now))['sequence']===1);
$db->exec("UPDATE codebridge_device_credentials SET revoked_at='".gmdate('Y-m-d H:i:s',$now)."' WHERE id='credential-1'");
try{$service->renew(str_repeat('a',48),$request,$now);throw new RuntimeException('Expected propagated device revocation');}catch(DomainException $error){check($error->getMessage()==='CODEBRIDGE_ACCESS_DENIED');}
check((int)$db->query('SELECT lease_sequence FROM codebridge_device_credentials')->fetchColumn()===1);$count++;

$db=database($now); $service=new CodeBridgeRenewalService($db,$signer);
$db->exec("UPDATE kslp_licenses SET revoked_at='".gmdate('Y-m-d H:i:s',$now)."' WHERE id='license-1'");
try{$service->renew(str_repeat('a',48),$request,$now);throw new RuntimeException('Expected propagated license revocation');}catch(DomainException $error){check($error->getMessage()==='CODEBRIDGE_ACCESS_DENIED');}
check((int)$db->query('SELECT lease_sequence FROM codebridge_device_credentials')->fetchColumn()===0);$count++;

// Lease enforcement: a client cannot claim a sequence ahead of authoritative storage.
$db=database($now); $service=new CodeBridgeRenewalService($db,$signer);
try{$service->renew(str_repeat('a',48),array_replace($request,['sequence'=>1]),$now);throw new RuntimeException('Expected sequence conflict');}catch(DomainException $error){check($error->getMessage()==='CODEBRIDGE_SEQUENCE_CONFLICT');}
check((int)$db->query('SELECT lease_sequence FROM codebridge_device_credentials')->fetchColumn()===0);
check((int)$db->query('SELECT COUNT(*) FROM kslp_license_events')->fetchColumn()===0);$count++;

$fixture=json_decode(file_get_contents($argv[1]),true,32,JSON_THROW_ON_ERROR);
$fixture['token']=$validToken;
file_put_contents($argv[1],json_encode($fixture,JSON_THROW_ON_ERROR));
echo "SQLite renewal checks: {$count} passed\n";
