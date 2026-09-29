<?php

declare(strict_types=1);

/*
 * Real-database concurrency regression for CodeBridge renewal.
 * Run only with CODEBRIDGE_CONCURRENCY_DSN pointing at an isolated PostgreSQL test database.
 * The harness deliberately refuses SQLite because SQLite does not model the row-lock behavior used in production.
 */
$strict=getenv('CODEBRIDGE_CONCURRENCY_REQUIRED') === '1';
$dsn=getenv('CODEBRIDGE_CONCURRENCY_DSN') ?: '';
if ($dsn === '') { fwrite($strict ? STDERR : STDOUT, "SKIP: CODEBRIDGE_CONCURRENCY_DSN not configured\n"); exit($strict ? 2 : 0); }
if (str_starts_with($dsn,'sqlite:')) { fwrite(STDERR,"SQLite is not a valid CodeBridge concurrency target\n"); exit(2); }

$user=getenv('CODEBRIDGE_CONCURRENCY_USER') ?: null;
$pass=getenv('CODEBRIDGE_CONCURRENCY_PASSWORD') ?: null;
$db=new PDO($dsn,$user,$pass,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
$driver=$db->getAttribute(PDO::ATTR_DRIVER_NAME);
if (!in_array($driver,['mysql','pgsql'],true)) { fwrite(STDERR,"Unsupported concurrency driver: {$driver}\n"); exit(2); }

require __DIR__.'/../../apps/platform/app/Services/Licensing/Kslp/KslpSigner.php';
require __DIR__.'/../../apps/platform/app/Services/Licensing/CodeBridge/CodeBridgeLeaseEncoder.php';
require __DIR__.'/../../apps/platform/app/Services/Licensing/CodeBridge/CodeBridgeRenewalService.php';

use App\Services\Licensing\CodeBridge\CodeBridgeRenewalService;
use App\Services\Licensing\Kslp\KslpSigner;

$pair=sodium_crypto_sign_keypair();
$signer=new class(sodium_crypto_sign_secretkey($pair)) implements KslpSigner {
    public function __construct(private string $key) {}
    public function kid(): string { return 'codebridge-concurrency-test'; }
    public function sign(string $message): string { return sodium_crypto_sign_detached($message,$this->key); }
};

$now=time(); $credential=str_repeat('r',48);
$db->beginTransaction();
try {
    foreach(['kslp_license_events','codebridge_device_credentials','kslp_activations','kslp_licenses','plans'] as $table){$db->exec("DELETE FROM {$table}");}
    $q=$db->prepare('INSERT INTO kslp_licenses (id,customer_id,product,plan,status,starts_at,expires_at,grace_until,revoked_at) VALUES (?,?,?,?,?,?,?,?,NULL)');
    $q->execute(['race-license','race-tenant','KMJ_CODEBRIDGE','professional','active',gmdate('Y-m-d H:i:s',$now-60),gmdate('Y-m-d H:i:s',$now+86400),gmdate('Y-m-d H:i:s',$now+172800)]);
    $q=$db->prepare('INSERT INTO kslp_activations (id,license_id,server_identity,deactivated_at) VALUES (?,?,?,NULL)');$q->execute(['race-activation','race-license','ed25519:race']);
    $q=$db->prepare('INSERT INTO codebridge_device_credentials (id,license_id,activation_id,tenant_id,device_id,server_identity,token_hash,lease_sequence,expires_at_epoch,revoked_at) VALUES (?,?,?,?,?,?,?,?,?,NULL)');
    $q->execute(['race-credential','race-license','race-activation','race-tenant','race-device','ed25519:race',hash('sha256',$credential),0,$now+86400]);
    $q=$db->prepare('INSERT INTO plans (code,features,limits,status) VALUES (?,?,?,?)');$q->execute(['codebridge.professional','{"read":true}','{"devices":1}','active']);
    $db->commit();
} catch(Throwable $e){$db->rollBack();throw $e;}

if (!function_exists('pcntl_fork')) { fwrite($strict ? STDERR : STDOUT, "SKIP: pcntl unavailable\n"); exit($strict ? 2 : 0); }
$dir=sys_get_temp_dir().'/codebridge-race-'.bin2hex(random_bytes(5)); mkdir($dir);
$request=['product'=>'KMJ_CODEBRIDGE','tenant'=>'race-tenant','device'=>'race-device','sequence'=>0];
$pids=[];
for($i=0;$i<2;$i++){
    $pid=pcntl_fork();
    if($pid===0){
        $child=new PDO($dsn,$user,$pass,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
        try{(new CodeBridgeRenewalService($child,$signer))->renew($credential,$request,$now);file_put_contents("{$dir}/{$i}",'ok');}
        catch(Throwable $e){file_put_contents("{$dir}/{$i}",get_class($e).':'.$e->getMessage());}
        exit(0);
    }
    $pids[]=$pid;
}
foreach($pids as $pid){pcntl_waitpid($pid,$status);}
$db=null;
$db=new PDO($dsn,$user,$pass,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
$results=[file_get_contents("{$dir}/0"),file_get_contents("{$dir}/1")];
$success=count(array_filter($results,fn($v)=>$v==='ok'));
$sequence=(int)$db->query("SELECT lease_sequence FROM codebridge_device_credentials WHERE id='race-credential'")->fetchColumn();
$events=(int)$db->query("SELECT COUNT(*) FROM kslp_license_events WHERE license_id='race-license' AND action='codebridge_lease_renewed'")->fetchColumn();
if($success!==2 || $sequence!==2 || $events!==2){throw new RuntimeException('Concurrent renewal serialization failed: '.json_encode(compact('results','sequence','events')));}

// Revocation must win before a subsequent renewal begins.
$db->exec("UPDATE codebridge_device_credentials SET revoked_at='".gmdate('Y-m-d H:i:s',$now)."' WHERE id='race-credential'");
try{(new CodeBridgeRenewalService($db,$signer))->renew($credential,['product'=>'KMJ_CODEBRIDGE','tenant'=>'race-tenant','device'=>'race-device','sequence'=>$sequence],$now);throw new RuntimeException('Revoked credential issued a lease');}
catch(DomainException $e){if($e->getMessage()!=='CODEBRIDGE_ACCESS_DENIED'){throw $e;}}
if((int)$db->query("SELECT lease_sequence FROM codebridge_device_credentials WHERE id='race-credential'")->fetchColumn()!==2){throw new RuntimeException('Revocation changed authoritative lease sequence');}
echo "CodeBridge real-DB concurrency checks: PASS\n";
