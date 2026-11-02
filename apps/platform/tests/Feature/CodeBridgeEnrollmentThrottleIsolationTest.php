<?php

namespace Tests\Feature;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

final class CodeBridgeEnrollmentThrottleIsolationTest extends TestCase
{
    use RefreshDatabase;

    public function test_polling_other_throttled_routes_does_not_starve_enrollment_start(): void
    {
        config()->set('codebridge.enabled', true);

        // Same client IP: exhaust the (separate) readiness and token budgets.
        for ($i = 0; $i < 12; $i++) {
            $this->getJson('/api/codebridge/v1/device-enrollments/readiness');
            $this->postJson('/api/codebridge/v1/device-enrollments/token', []);
        }

        // Enrollment start must still reach validation, not be rate limited.
        $this->postJson('/api/codebridge/v1/device-enrollments', [])->assertStatus(422);
    }

    public function test_enrollment_start_itself_is_still_rate_limited_after_ten_attempts(): void
    {
        config()->set('codebridge.enabled', true);

        for ($i = 0; $i < 10; $i++) {
            $this->postJson('/api/codebridge/v1/device-enrollments', [])->assertStatus(422);
        }

        $this->postJson('/api/codebridge/v1/device-enrollments', [])
            ->assertStatus(429)
            ->assertHeader('Retry-After');
    }

    public function test_exhausted_enrollment_start_budget_does_not_throttle_readiness(): void
    {
        config()->set('codebridge.enabled', true);

        for ($i = 0; $i < 11; $i++) {
            $this->postJson('/api/codebridge/v1/device-enrollments', []);
        }

        self::assertNotSame(429, $this->getJson('/api/codebridge/v1/device-enrollments/readiness')->getStatusCode());
    }
}
