<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

final class CodeBridgeLocalTelemetryHttpTest extends TestCase
{
    use RefreshDatabase;

    public function test_anonymous_sessions_cannot_read_cross_tenant_model_or_queue_metrics(): void
    {
        $this->getJson('/services/kmj-codebridge/telemetry?tenant_id=tenant-a')
            ->assertUnauthorized();
    }

    public function test_authenticated_user_without_organization_access_cannot_read_telemetry(): void
    {
        $user = User::factory()->create(['email_verified_at' => now()]);
        $this->actingAs($user)
            ->getJson('/services/kmj-codebridge/telemetry?tenant_id=tenant-a')
            ->assertNotFound();
    }

    public function test_missing_device_bearer_token_fails_closed(): void
    {
        config()->set('codebridge.enabled', true);
        $this->postJson('/api/codebridge/v1/telemetry', [
            'project_id' => 'kmj-main-platform',
            'ollama' => ['reachable' => true, 'models' => ['qwen3:4b']],
            'queue' => ['queued' => 100, 'running' => 1, 'waiting' => 0],
        ])->assertUnauthorized();
    }

    public function test_unregistered_bearer_token_cannot_inject_fake_device_counts(): void
    {
        config()->set('codebridge.enabled', true);
        $this->withToken(str_repeat('z', 64))
            ->postJson('/api/codebridge/v1/telemetry', [
                'project_id' => 'kmj-main-platform',
                'ollama' => ['reachable' => true, 'models' => ['qwen3:4b']],
                'queue' => ['queued' => 400, 'running' => 1, 'waiting' => 0],
            ])->assertUnauthorized();
    }

    public function test_oversized_telemetry_payload_is_refused_without_db_or_model_access(): void
    {
        config()->set('codebridge.enabled', true);
        $this->call('POST', '/api/codebridge/v1/telemetry', [], [], [], [
            'CONTENT_TYPE' => 'application/json',
            'HTTP_AUTHORIZATION' => 'Bearer '.str_repeat('z', 64),
        ], json_encode(['payload' => str_repeat('x', 4100)], JSON_THROW_ON_ERROR))
            ->assertStatus(413);
    }
}
