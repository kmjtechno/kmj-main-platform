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
        $r = app(KslpKeyRegistry::class);
        $r->publish('lic-public-1', 'license', 'PUBLIC-KEY-MATERIAL');
        $this->getJson('/api/v1/kslp/contract')->assertOk()
            ->assertHeader('Access-Control-Allow-Origin', '*')
            ->assertJsonPath('protocol_version', 'KSLP-v1')
            ->assertJsonStructure(['contract_sha256', 'algorithms']);
        $res = $this->getJson('/api/v1/kslp/keys/license')->assertOk()
            ->assertHeader('Access-Control-Allow-Origin', '*')
            ->assertJsonPath('purpose', 'license')->json();
        self::assertSame('PUBLIC-KEY-MATERIAL', $res['keys'][0]['public_key']);
        self::assertArrayNotHasKey('private_key', $res['keys'][0]);
    }
}
