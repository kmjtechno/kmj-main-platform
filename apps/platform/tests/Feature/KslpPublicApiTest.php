<?php

namespace Tests\Feature;

use App\Services\Licensing\Kslp\KslpKeyRegistry;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

final class KslpPublicApiTest extends TestCase
{
    use RefreshDatabase;

    private function key(string $seed): array
    {
        $pair = sodium_crypto_sign_seed_keypair(hash('sha256', $seed, true));
        $raw = sodium_crypto_sign_publickey($pair);
        $encoded = rtrim(strtr(base64_encode($raw), '+/', '-_'), '=');

        return [$raw, $encoded];
    }

    public function test_contract_and_public_verification_keys_are_versioned_and_private_key_free(): void
    {
        [$rawPublic, $encoded] = $this->key('api-public');
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
        self::assertSame($rawPublic, $registry->publicKey('lic-public-1', 'license'));
        self::assertArrayNotHasKey('private_key', $response['keys'][0]);
    }

    public function test_omnidesk_key_endpoint_emits_only_bounded_current_ed25519_keys(): void
    {
        [$rawActive, $active] = $this->key('omnidesk-active');
        [, $unbounded] = $this->key('omnidesk-unbounded');
        [, $future] = $this->key('omnidesk-future');

        $registry = app(KslpKeyRegistry::class);
        $registry->publish('omni-active', 'license', $active);
        $registry->publish('omni-unbounded', 'license', $unbounded);
        $registry->publish('omni-future', 'license', $future, 'retiring');

        DB::table('kslp_signing_keys')->where('kid', 'omni-active')->update([
            'not_before' => now()->subHour(),
            'not_after' => now()->addDay(),
        ]);
        DB::table('kslp_signing_keys')->where('kid', 'omni-future')->update([
            'not_before' => now()->addHour(),
            'not_after' => now()->addDay(),
        ]);

        $response = $this->getJson('/api/v1/licensing/keys')
            ->assertOk()
            ->assertHeader('Access-Control-Allow-Origin', '*')
            ->assertJsonPath('protocol_version', 'KSLP-v1')
            ->assertJsonPath('contract_version', 'kmj.omnidesk.license.v1')
            ->assertJsonPath('product_id', 'KMJ_OMNIDESK')
            ->assertJsonPath('algorithm', 'Ed25519')
            ->json();

        self::assertCount(1, $response['keys']);
        self::assertSame('omni-active', $response['keys'][0]['kid']);
        self::assertSame('Ed25519', $response['keys'][0]['algorithm']);
        self::assertSame(base64_encode($rawActive), $response['keys'][0]['public_key_base64']);
        self::assertSame('ACTIVE', $response['keys'][0]['status']);
        self::assertIsInt($response['keys'][0]['not_before']);
        self::assertIsInt($response['keys'][0]['not_after']);
        self::assertArrayNotHasKey('private_key', $response['keys'][0]);
    }
}
