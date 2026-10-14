<?php

namespace Tests\Feature;

use App\Services\Licensing\Kslp\KslpKeyRegistry;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

final class KslpKeyRotationTest extends TestCase
{
    use RefreshDatabase;

    private function key(string $seed): string
    {
        $pair = sodium_crypto_sign_seed_keypair(hash('sha256', $seed, true));

        return rtrim(strtr(base64_encode(sodium_crypto_sign_publickey($pair)), '+/', '-_'), '=');
    }

    public function test_key_domains_rotation_and_revocation_are_separate(): void
    {
        $registry = app(KslpKeyRegistry::class);
        $registry->publish('lic-1', 'license', $this->key('pub1'));
        $registry->publish('lic-2', 'license', $this->key('pub2'), 'retiring');
        $registry->publish('rel-1', 'release', $this->key('relpub'));
        $registry->publish('ev-1', 'evidence', $this->key('evpub'));

        self::assertCount(2, $registry->discovery('license'));
        self::assertCount(1, $registry->discovery('release'));
        self::assertCount(1, $registry->discovery('evidence'));

        $registry->revoke('lic-1');
        self::assertCount(1, $registry->discovery('license'));
    }

    public function test_existing_kid_cannot_change_key_material_or_trust_domain(): void
    {
        $registry = app(KslpKeyRegistry::class);
        $registry->publish('lic-stable', 'license', $this->key('original'));

        foreach ([
            ['license', $this->key('replacement')],
            ['release', $this->key('original')],
        ] as [$purpose, $publicKey]) {
            try {
                $registry->publish('lic-stable', $purpose, $publicKey);
                self::fail('A key id must be immutable.');
            } catch (DomainException $exception) {
                self::assertSame('KSLP_KEY_IDENTITY_CONFLICT', $exception->getMessage());
            }
        }

        $pair = sodium_crypto_sign_seed_keypair(hash('sha256', 'original', true));
        self::assertSame(
            sodium_crypto_sign_publickey($pair),
            $registry->publicKey('lic-stable', 'license')
        );
    }

    public function test_revoked_kid_cannot_be_republished(): void
    {
        $registry = app(KslpKeyRegistry::class);
        $registry->publish('lic-dead', 'license', $this->key('dead'));
        $registry->revoke('lic-dead');

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('KSLP_KEY_REVOKED');

        $registry->publish('lic-dead', 'license', $this->key('dead'));
    }

    public function test_rejects_malformed_noncanonical_public_keys_and_invalid_key_ids(): void
    {
        $registry = app(KslpKeyRegistry::class);
        foreach (['PUBLIC-KEY-MATERIAL', '', str_repeat('A', 42), str_repeat('A', 44),
            str_repeat('!', 43), str_repeat('A', 42).'B'] as $malformed) {
            try {
                $registry->publish('bad', 'license', $malformed);
                self::fail('Malformed key was accepted.');
            } catch (DomainException $e) {
                self::assertSame('KSLP_INVALID_PUBLIC_KEY', $e->getMessage());
            }
        }

        $this->expectExceptionMessage('KSLP_INVALID_PUBLIC_KEY');
        $registry->publish('../invalid', 'license', $this->key('valid'));
    }

    public function test_not_before_and_not_after_are_enforced_in_discovery_and_verification(): void
    {
        $registry = app(KslpKeyRegistry::class);
        $public = $this->key('future');
        $registry->publish('future-key', 'license', $public);
        DB::table('kslp_signing_keys')
            ->where('kid', 'future-key')
            ->update(['not_before' => now()->addDay()]);

        self::assertSame([], $registry->discovery('license'));
        try {
            $registry->publicKey('future-key', 'license');
            self::fail('Future key should not verify.');
        } catch (DomainException $e) {
            self::assertSame('KSLP_UNKNOWN_KID', $e->getMessage());
        }

        DB::table('kslp_signing_keys')
            ->where('kid', 'future-key')
            ->update(['not_before' => now()->subDays(2), 'not_after' => now()->subDay()]);
        self::assertSame([], $registry->discovery('license'));
        $this->expectExceptionMessage('KSLP_UNKNOWN_KID');
        $registry->publicKey('future-key', 'license');
    }
}
