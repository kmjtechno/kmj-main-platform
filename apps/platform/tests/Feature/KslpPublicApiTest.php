<?php

namespace Tests\Feature;

use App\Services\Licensing\Kslp\KslpKeyRegistry;
use App\Services\Licensing\OmniDeskLicenseContract;
use DomainException;
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
        [, $otherProduct] = $this->key('cloudos-bound');

        $registry = app(KslpKeyRegistry::class);
        $registry->publish(
            'omni-active', 'license', $active, 'active',
            OmniDeskLicenseContract::PRODUCT_ID, now()->addDay(),
        );
        // Unscoped legacy keys and keys scoped to other products must never
        // be accepted by the OmniDesk verifier even when temporally valid.
        $registry->publish('omni-unbounded', 'license', $unbounded);
        $registry->publish(
            'cloudos-bound', 'license', $otherProduct, 'active',
            'KMJ_CLOUDOS', now()->addDay(),
        );
        $registry->publish(
            'omni-future', 'license', $future, 'retiring',
            OmniDeskLicenseContract::PRODUCT_ID, now()->addDay(),
        );

        DB::table('kslp_signing_keys')->where('kid', 'omni-future')->update([
            'not_before' => now()->addHour(),
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

    public function test_omnidesk_requires_bounded_product_scoped_key_identity(): void
    {
        [, $generic] = $this->key('legacy-generic');
        [, $scoped] = $this->key('explicit-omnidesk');
        $registry = app(KslpKeyRegistry::class);

        $registry->publish('legacy-kid', 'license', $generic);
        $expires = now()->addDay();

        try {
            $registry->publish(
                'legacy-kid', 'license', $generic, 'active',
                OmniDeskLicenseContract::PRODUCT_ID, $expires,
            );
            self::fail('An unscoped kid must never acquire OmniDesk issuer authority.');
        } catch (DomainException $error) {
            self::assertSame('KSLP_KEY_IDENTITY_CONFLICT', $error->getMessage());
        }

        try {
            $registry->publish(
                'no-expiry', 'license', $scoped, 'active',
                OmniDeskLicenseContract::PRODUCT_ID,
            );
            self::fail('OmniDesk scope requires finite key validity.');
        } catch (DomainException $error) {
            self::assertSame('KSLP_INVALID_KEY_SCOPE', $error->getMessage());
        }

        $registry->publish(
            'bounded-omni', 'license', $scoped, 'active',
            OmniDeskLicenseContract::PRODUCT_ID, $expires,
        );
        self::assertSame(
            sodium_crypto_sign_publickey(sodium_crypto_sign_seed_keypair(hash('sha256', 'explicit-omnidesk', true))),
            $registry->publicKey('bounded-omni', 'license', OmniDeskLicenseContract::PRODUCT_ID),
        );

        try {
            $registry->publicKey('bounded-omni', 'license', 'KMJ_CLOUDOS');
            self::fail('Other-product callers must not resolve OmniDesk key IDs.');
        } catch (DomainException $error) {
            self::assertSame('KSLP_UNKNOWN_KID', $error->getMessage());
        }

        try {
            $registry->publish(
                'bounded-omni', 'license', $scoped, 'active',
                OmniDeskLicenseContract::PRODUCT_ID, now()->addDays(2),
            );
            self::fail('An existing key validity window cannot be silently extended.');
        } catch (DomainException $error) {
            self::assertSame('KSLP_KEY_WINDOW_CONFLICT', $error->getMessage());
        }
    }

}
