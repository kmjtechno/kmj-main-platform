<?php

namespace App\Services\Licensing\Kslp;

use DomainException;

final class KslpEvidenceManifest
{
    public function sign(array $facts, KslpEvidenceSigner $signer): array
    {
        $required = ['gate_id', 'verdict', 'release_id', 'contract_sha256', 'main_platform_sha', 'cloudos_sha', 'started_at', 'finished_at', 'environment', 'node_ids', 'test_command', 'tests', 'artifacts', 'previous_manifest_sha256'];
        foreach ($required as $k) {
            if (! array_key_exists($k, $facts)) {
                throw new DomainException('KSLP_EVIDENCE_INCOMPLETE');
            }
        }if (! in_array($facts['verdict'], ['PASS', 'FAIL', 'INCOMPLETE', 'INVALID'], true)) {
            throw new DomainException('KSLP_EVIDENCE_INVALID_VERDICT');
        }$m = $facts + ['schema_version' => 'KSLP-EVIDENCE-v1', 'kslp_version' => 'KSLP-v1'];
        $m['signing'] = ['algorithm' => 'Ed25519', 'key_id' => $signer->keyId(), 'signature' => ''];
        self::sort($m);
        $payload = json_encode($m, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR);
        $sig = $signer->sign($payload);
        if ($sig === '') {
            throw new DomainException('KSLP_EVIDENCE_SIGNING_FAILED');
        }$m['signing']['signature'] = rtrim(strtr(base64_encode($sig), '+/', '-_'), '=');

        return $m;
    }

    private static function sort(array &$v): void
    {
        ksort($v);
        foreach ($v as &$x) {
            if (is_array($x)) {
                self::sort($x);
            }
        }
    }
}
