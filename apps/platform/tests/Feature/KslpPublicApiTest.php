<?php

namespace Tests\Feature;

use App\Services\Licensing\Kslp\KslpKeyRegistry;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

final class KslpPublicApiTest extends TestCase
{
    use RefreshDatabase;

    private function key(string $seed): string
    {
        $pair = sodium_crypto_sign_seed_keypair(hash('sha256', $seed, true));

        return rtrim(strtr(base64_encode(sodium_crypto_sign_publickey($pair)), '+/', '-_'), '=');
    }

    public function test_contract_and_public_verification_keys_are_versioned_and_private_key_free(): void
    {
        $encoded = $this->key('api-public');
        $registry = app(KslpKeyRegistry::class);
        $registry->publish('lic-public-1', 'license', $encoded);

        $this->getJson('/api/v1/kslp/contract')
            ->assertOk()
            ->assertHeader('Access-Control-Allow-Origin', '*')
            ->assertJsonPath('protocol_version', 'KSLP-v1')
            ->assertJsonStructure(['contract_sha256', 'algorithms']);

        $response = $this->getJson('/api/v1/kslp/keys/license')
            ->assertOk()
            ->assertHeader('Access-Control-Allow-Origin', '*')
            ->assertJsonPath('purpose', 'license')
            ->json();

        self::assertSame($encoded, $response['keys'][0]['public_key']);
        self::assertArrayNotHasKey('private_key', $response['keys'][0]);
    }

    public function test_omnidesk_compatibility_key_endpoint_matches_the_client_contract(): void
    {
        $registry = app(KslpKeyRegistry::class);
        $active = $this->key('omnidesk-active');
        $rollover = $this->key('omnidesk-rollover');
        $registry->publish('omnidesk-active', 'license', $active);
        $registry->publish('omnidesk-rollover', 'license', $rollover, 'retiring');

        $response = $this->getJson('/api/v1/licensing/keys')
            ->assertOk()
            ->assertHeader('Access-Control-Allow-Origin', '*')
            ->assertHeader('X-Content-Type-Options', 'nosniff')
            ->assertJsonPath('protocol_version', 'KSLP-v1')
            ->assertJsonPath('contract_version', 'kmj.omnidesk.license.v1')
            ->assertJsonPath('product_id', 'KMJ_OMNIDESK')
            ->assertJsonPath('product_slug', 'kmj-omnidesk')
            ->json();

        self::assertCount(2, $response['keys']);
        self::assertSame(
            ['algorithm', 'kid', 'not_after', 'not_before', 'public_key', 'status'],
            array_keys(array_diff_key($response['keys'][0], []))
        );
        self::assertSame('omnidesk-active', $response['keys'][0]['kid']);
        self::assertSame('Ed25519', $response['keys'][0]['algorithm']);
        self::assertSame($active, $response['keys'][0]['public_key']);
        self::assertSame('ACTIVE', $response['keys'][0]['status']);
        self::assertIsInt($response['keys'][0]['not_before']);
        self::assertNull($response['keys'][0]['not_after']);
        self::assertSame('ROLLOVER', $response['keys'][1]['status']);
        self::assertArrayNotHasKey('private_key', $response['keys'][0]);
    }
}
