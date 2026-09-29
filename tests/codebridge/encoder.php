<?php

declare(strict_types=1);

require __DIR__.'/../../apps/platform/app/Services/Licensing/Kslp/KslpSigner.php';
require __DIR__.'/../../apps/platform/app/Services/Licensing/CodeBridge/CodeBridgeLeaseEncoder.php';

use App\Services\Licensing\CodeBridge\CodeBridgeLeaseEncoder;
use App\Services\Licensing\Kslp\KslpSigner;

$pair = sodium_crypto_sign_keypair();
$signer = new class(sodium_crypto_sign_secretkey($pair)) implements KslpSigner {
    public function __construct(private string $key) {}
    public function kid(): string { return 'codebridge-test'; }
    public function sign(string $message): string { return sodium_crypto_sign_detached($message, $this->key); }
};
$now = 1800000000;
$claims = ['v' => 1, 'product' => 'KMJ_CODEBRIDGE', 'tenant' => 'customer-1', 'device' => 'device-1', 'license_id' => 'license-1', 'activation_id' => 'activation-1', 'jti' => 'token-1', 'sequence' => 1, 'iat' => $now, 'nbf' => $now, 'exp' => $now + 86400, 'grace_until' => $now + 86400 + 172800, 'features' => ['read', 'write', 'execute'], 'limits' => ['devices' => 2, 'concurrent_jobs' => 2]];
$encoder = new CodeBridgeLeaseEncoder();
$token = $encoder->encode($claims, $signer, $now);
$count = 1;
foreach ([['product' => 'KMJ_CLOUDOS'], ['tenant' => '../bad'], ['device' => ''], ['exp' => $now - 1], ['iat' => $now + 1], ['nbf' => $now + 1], ['sequence' => 0], ['sequence' => '1'], ['features' => ['admin']], ['limits' => ['devices' => 2, 'concurrent_jobs' => 17]], ['grace_until' => $now + 300000], ['unexpected' => true], ['license_id' => ' '], ['exp' => $now + 86401]] as $change) {
    try {
        $encoder->encode(array_replace($claims, $change), $signer, $now);
        throw new RuntimeException('Expected validation failure');
    } catch (DomainException) { $count++; }
}
// Only ephemeral public verification material leaves this process.
$public = sodium_crypto_sign_publickey($pair);
$der = hex2bin('302a300506032b6570032100').$public;
$pem = "-----BEGIN PUBLIC KEY-----\n".chunk_split(base64_encode($der), 64, "\n")."-----END PUBLIC KEY-----\n";
file_put_contents($argv[1], json_encode(['token' => $token, 'keys' => ['codebridge-test' => $pem], 'binding' => ['tenant' => 'customer-1', 'device' => 'device-1'], 'now' => $now], JSON_THROW_ON_ERROR));
echo "PHP encoder checks: {$count} passed\n";
