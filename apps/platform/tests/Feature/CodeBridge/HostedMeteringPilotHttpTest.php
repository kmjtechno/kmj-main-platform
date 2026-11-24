<?php

declare(strict_types=1);

namespace Tests\Feature\CodeBridge;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Str;
use Tests\TestCase;

final class HostedMeteringPilotHttpTest extends TestCase
{
    use RefreshDatabase;

    public function test_pilot_is_disabled_by_default(): void
    {
        config()->set('codebridge.enabled', true);
        $this->postJson('/api/codebridge/v1/hosted-metering-pilot', [])->assertStatus(503);
    }

    public function test_dedicated_token_and_exact_tenant_are_required(): void
    {
        $tenant = (string) Str::uuid();
        $token = str_repeat('a', 43);
        config()->set('codebridge.enabled', true);
        config()->set('codebridge.hosted_metering_pilot_enabled', true);
        config()->set('codebridge.hosted_metering_pilot_tenant', $tenant);
        config()->set('codebridge.hosted_metering_pilot_token_hash', hash('sha256', $token));

        $this->postJson('/api/codebridge/v1/hosted-metering-pilot', [])->assertForbidden();
        $this->withToken($token)->postJson('/api/codebridge/v1/hosted-metering-pilot', [
            'action' => 'reserve',
            'organization_id' => (string) Str::uuid(),
            'execution_id' => (string) Str::uuid(),
        ])->assertStatus(422);
        $this->withToken($token)->postJson('/api/codebridge/v1/hosted-metering-pilot', [
            'action' => 'settle',
            'organization_id' => $tenant,
            'execution_id' => (string) Str::uuid(),
            'outcome' => 'succeeded',
            'signature' => 'invalid',
        ])->assertStatus(409);
        $this->assertDatabaseCount('codebridge_usage_periods', 0);
        $this->assertDatabaseCount('codebridge_receipt_bindings', 0);
    }
}
