<?php

namespace Tests\Feature;

use App\Services\Licensing\Kslp\KslpKeyRegistry;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

final class KslpKeyRotationTest extends TestCase
{
    use RefreshDatabase;

    public function test_key_domains_rotation_and_revocation_are_separate(): void
    {
        $registry = app(KslpKeyRegistry::class);
        $registry->publish('lic-1', 'license', 'pub1');
        $registry->publish('lic-2', 'license', 'pub2', 'retiring');
        $registry->publish('rel-1', 'release', 'relpub');
        $registry->publish('ev-1', 'evidence', 'evpub');

        self::assertCount(2, $registry->discovery('license'));
        self::assertCount(1, $registry->discovery('release'));
        self::assertCount(1, $registry->discovery('evidence'));

        $registry->revoke('lic-1');
        self::assertCount(1, $registry->discovery('license'));
    }

    public function test_existing_kid_cannot_change_key_material_or_trust_domain(): void
    {
        $registry = app(KslpKeyRegistry::class);
        $registry->publish('lic-stable', 'license', 'pub-original');

        foreach ([
            ['license', 'pub-replacement'],
            ['release', 'pub-original'],
        ] as [$purpose, $publicKey]) {
            try {
                $registry->publish('lic-stable', $purpose, $publicKey);
                self::fail('A key id must be immutable.');
            } catch (DomainException $exception) {
                self::assertSame('KSLP_KEY_IDENTITY_CONFLICT', $exception->getMessage());
            }
        }

        self::assertSame('pub-original', $registry->publicKey('lic-stable', 'license'));
    }

    public function test_revoked_kid_cannot_be_republished(): void
    {
        $registry = app(KslpKeyRegistry::class);
        $registry->publish('lic-dead', 'license', 'pub-dead');
        $registry->revoke('lic-dead');

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('KSLP_KEY_REVOKED');

        $registry->publish('lic-dead', 'license', 'pub-dead');
    }
}
