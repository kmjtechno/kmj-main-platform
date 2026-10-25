<?php

declare(strict_types=1);

namespace Tests\Feature;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

/**
 * This contract is safe to call before a short-lived device enrollment.
 * It never creates a pairing/device/license row, exposes an upstream URL,
 * rotates a secret, or mistakes a 401 agent challenge for READY.
 */
final class CodeBridgeEnrollmentReadinessTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();

        config()->set('codebridge.enabled', true);
        config()->set('app.url', 'https://kmjtechno.com');
        config()->set('services.codebridge_gateway.url', 'http://127.0.0.1:18787');
        config()->set('services.codebridge_gateway.agent_public_url', 'https://kmjtechno.com');
    }

    public function test_current_config_returns_compatibility_only_without_credentials_or_mutation(): void
    {
        $this->getJson('/api/codebridge/v1/device-enrollments/readiness')
            ->assertOk()
            ->assertExactJson(['pairing_config' => 'ready', 'protocol' => 2]);

        // A readiness check cannot register a device or consume a license.
        self::assertDatabaseCount('codebridge_device_pairings', 0);
        self::assertDatabaseCount('codebridge_device_credentials', 0);
        self::assertDatabaseCount('kslp_activations', 0);
    }

    public function test_feature_gate_disabled_fails_closed(): void
    {
        config()->set('codebridge.enabled', false);

        $this->getJson('/api/codebridge/v1/device-enrollments/readiness')
            ->assertStatus(503)
            ->assertExactJson(['pairing_config' => 'unavailable']);
    }

    public function test_legacy_private_loopback_origin_cannot_advertise_pairing_ready(): void
    {
        config()->set('services.codebridge_gateway.agent_public_url', 'http://127.0.0.1:18787');

        $this->getJson('/api/codebridge/v1/device-enrollments/readiness')
            ->assertStatus(503)
            ->assertExactJson(['pairing_config' => 'unavailable']);
    }

    public function test_missing_or_foreign_public_origin_fails_closed(): void
    {
        foreach ([
            '',
            'https://other.example',
            'https://kmjtechno.com.evil.example',
            'https://kmjtechno.com/path',
            'https://kmjtechno.com?token=secret',
            'https://user:pass@kmjtechno.com',
            'http://kmjtechno.com',
            'https://kmjtechno.com:444',
        ] as $invalid) {
            config()->set('services.codebridge_gateway.agent_public_url', $invalid);
            $this->getJson('/api/codebridge/v1/device-enrollments/readiness')
                ->assertStatus(503)
                ->assertExactJson(['pairing_config' => 'unavailable']);
        }
    }

    public function test_invalid_canonical_application_origin_also_fails_closed(): void
    {
        config()->set('app.url', 'http://kmjtechno.com');

        $this->getJson('/api/codebridge/v1/device-enrollments/readiness')
            ->assertStatus(503)
            ->assertExactJson(['pairing_config' => 'unavailable']);
    }
}
