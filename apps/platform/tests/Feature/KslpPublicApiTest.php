<?php

namespace Tests\Feature;

use App\Services\Licensing\Kslp\KslpKeyRegistry;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

final class KslpPublicApiTest extends TestCase
{
    use RefreshDatabase;

    public function test_contract_and_public_verification_keys_are_versioned_and_private_key_free(): void
    {
        $pair = sodium_crypto_sign_seed_keypair(hash('sha256', 'api-public', true));
        $rawPublic = sodium_crypto_sign_publickey($pair);
        $encoded = rtrim(strtr(base64_encode($rawPublic), '+/', '-_'), '=');
        $registry = app(KslpKeyRegistry::class);
        $registry->publish('lic-public-1', 'license', $encoded);
        $this->getJson('/api/v1/kslp/contract')
            ->assertOk()
            ->assertJsonPath('protocol_version', 'KSLP-v1')
            ->assertJsonStructure(['contract_sha256', 'algorithms']);

        $response = $this->getJson('/api/v1/kslp/keys/license')
            ->assertOk()
            ->assertJsonPath('purpose', 'license')->json();

        self::assertSame($encoded, $response['keys'][0]['public_key']);
        self::assertSame($rawPublic, $registry->publicKey('lic-public-1', 'license'));
        self::assertArrayNotHasKey('private_key', $response['keys'][0]);
    }
}
