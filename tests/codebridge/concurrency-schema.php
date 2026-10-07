<?php
declare(strict_types=1);
$dsn=getenv('CODEBRIDGE_CONCURRENCY_DSN') ?: throw new RuntimeException('Missing CODEBRIDGE_CONCURRENCY_DSN');
$db=new PDO($dsn,getenv('CODEBRIDGE_CONCURRENCY_USER')?:null,getenv('CODEBRIDGE_CONCURRENCY_PASSWORD')?:null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
$driver=$db->getAttribute(PDO::ATTR_DRIVER_NAME);
if($driver!=='pgsql'){throw new RuntimeException('Real PostgreSQL required');}
foreach(['kslp_license_events','codebridge_device_credentials','kslp_activations','kslp_licenses','plans'] as $t){$db->exec("DROP TABLE IF EXISTS {$t}");}
$db->exec('CREATE TABLE plans (code VARCHAR(160) PRIMARY KEY, features TEXT, limits TEXT, status VARCHAR(32))');
$db->exec('CREATE TABLE kslp_licenses (id VARCHAR(64) PRIMARY KEY, customer_id VARCHAR(64), product VARCHAR(64), plan VARCHAR(64), status VARCHAR(32), starts_at TIMESTAMP, expires_at TIMESTAMP, grace_until TIMESTAMP NULL, revoked_at TIMESTAMP NULL)');
$db->exec('CREATE TABLE kslp_activations (id VARCHAR(64) PRIMARY KEY, license_id VARCHAR(64), server_identity VARCHAR(160), deactivated_at TIMESTAMP NULL)');
$db->exec('CREATE TABLE codebridge_device_credentials (id VARCHAR(64) PRIMARY KEY, license_id VARCHAR(64), activation_id VARCHAR(64), tenant_id VARCHAR(64), device_id VARCHAR(64), server_identity VARCHAR(160), token_hash CHAR(64) UNIQUE, lease_sequence BIGINT, expires_at_epoch BIGINT, revoked_at TIMESTAMP NULL)');
$id='BIGSERIAL PRIMARY KEY';
$db->exec("CREATE TABLE kslp_license_events (id {$id}, license_id VARCHAR(64), actor_id VARCHAR(160), action VARCHAR(160), reason VARCHAR(255), correlation_id VARCHAR(64), metadata TEXT, created_at TIMESTAMP)");
echo "CodeBridge concurrency schema ready on {$driver}\n";
