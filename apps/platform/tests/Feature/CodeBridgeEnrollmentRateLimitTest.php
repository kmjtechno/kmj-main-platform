<?php

declare(strict_types=1);

namespace Tests\Feature;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

final class CodeBridgeEnrollmentRateLimitTest extends TestCase
{
    use RefreshDatabase;

    /** @return array<string, mixed> */
    private function enrollment(string $deviceId): array
    {
        return [
            'product' => 'KMJ_CODEBRIDGE',
            'device' => [
                'id' => $deviceId,
                'name' => 'P520 CodeBridge Agent',
                'platform' => 'win32',
                'arch' => 'x64',
            ],
            'project' => ['id' => 'vioso-clone', 'name' => 'VIOSO Clone'],
            'requested_permissions' => ['read', 'write', 'execute'],
            'code_challenge' => str_repeat('a', 43),
            'code_challenge_method' => 'S256',
        ];
    }

    public function test_one_device_is_still_capped_at_ten_requests_per_minute(): void
    {
        config()->set('codebridge.enabled', true);
        $this->withServerVariables(['REMOTE_ADDR' => '198.51.100.31']);

        for ($attempt = 0; $attempt < 10; $attempt++) {
            $this->postJson('/api/codebridge/v1/device-enrollments', $this->enrollment('p520-vioso-v3'))
                ->assertCreated();
        }

        $this->postJson('/api/codebridge/v1/device-enrollments', $this->enrollment('p520-vioso-v3'))
            ->assertStatus(429)
            ->assertHeader('Retry-After');

        // The abusive identity's throttle must not suppress an independent
        // scoped project agent behind the same office IP address.
        $this->postJson('/api/codebridge/v1/device-enrollments', $this->enrollment('p520-calibration-v3'))
            ->assertCreated();
    }

    public function test_distinct_devices_can_enroll_behind_one_public_ip_without_early_429(): void
    {
        config()->set('codebridge.enabled', true);
        $this->withServerVariables(['REMOTE_ADDR' => '198.51.100.32']);

        for ($device = 1; $device <= 11; $device++) {
            $this->postJson(
                '/api/codebridge/v1/device-enrollments',
                $this->enrollment('p520-project-'.$device),
            )->assertCreated();
        }
    }

    public function test_malformed_ids_share_a_strict_per_ip_limit(): void
    {
        config()->set('codebridge.enabled', true);
        $this->withServerVariables(['REMOTE_ADDR' => '198.51.100.33']);

        for ($attempt = 0; $attempt < 10; $attempt++) {
            $this->postJson(
                '/api/codebridge/v1/device-enrollments',
                $this->enrollment('../malformed-'.$attempt),
            )->assertUnprocessable();
        }

        $this->postJson(
            '/api/codebridge/v1/device-enrollments',
            $this->enrollment('../malformed-last'),
        )->assertStatus(429);
    }
}
