<?php

namespace Tests\Unit\Kslp;

use App\Services\Licensing\Kslp\KslpEvidenceManifest;
use App\Services\Licensing\Kslp\KslpEvidenceSigner;
use PHPUnit\Framework\TestCase;

final class KslpEvidenceManifestTest extends TestCase
{
    public function test_manifest_uses_separate_ed25519_evidence_signer(): void
    {
        $kp = sodium_crypto_sign_keypair();
        $sk = sodium_crypto_sign_secretkey($kp);
        $pk = sodium_crypto_sign_publickey($kp);
        $s = new class($sk)implements KslpEvidenceSigner
        {
            public function __construct(private string $sk) {}

            public function keyId(): string
            {
                return 'evidence-test';
            }

            public function sign(string $m): string
            {
                return sodium_crypto_sign_detached($m, $this->sk);
            }
        };
        $facts = ['gate_id' => 'CONTRACT', 'verdict' => 'PASS', 'release_id' => 'test', 'contract_sha256' => str_repeat('a', 64), 'main_platform_sha' => str_repeat('b', 40), 'cloudos_sha' => str_repeat('c', 40), 'started_at' => '2026-09-27T00:00:00Z', 'finished_at' => '2026-09-27T00:01:00Z', 'environment' => 'test', 'node_ids' => ['node-1'], 'test_command' => 'test', 'tests' => ['passed' => 1, 'failed' => 0, 'skipped' => 0], 'artifacts' => [], 'previous_manifest_sha256' => null];
        $m = (new KslpEvidenceManifest)->sign($facts, $s);
        $sig = base64_decode(strtr($m['signing']['signature'], '-_', '+/'));
        $m['signing']['signature'] = '';
        $this->sort($m);
        $payload = json_encode($m, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR);
        self::assertTrue(sodium_crypto_sign_verify_detached($sig, $payload, $pk));
    }

    private function sort(array &$v): void
    {
        ksort($v);
        foreach ($v as &$x) {
            if (is_array($x)) {
                $this->sort($x);
            }
        }
    }
}
