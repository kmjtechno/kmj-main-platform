<?php

namespace Tests\Feature;

use App\Models\OperatorActionAudit;
use App\Models\User;
use App\Services\Operations\CodeBridgeStageDispatcher;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Http;
use RuntimeException;
use Tests\TestCase;

final class CodeBridgeStageDispatcherTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        Cache::forget('kmj-codebridge-stage:owner-v1');
        Http::preventStrayRequests();
        config()->set('services.codebridge_stage.github_token', 'test-only-github-token');
    }

    public function test_dispatch_pins_main_checks_active_workflow_and_audits_204_without_live_claim(): void
    {
        Http::fake([
            'https://api.github.com/repos/kmjtechno/kmj-codebridge/commits/main' => Http::response(
                ['sha' => str_repeat('a', 40)],
                200,
            ),
            'https://api.github.com/repos/kmjtechno/kmj-codebridge/actions/workflows/oneclick-stage.yml/runs*' =>
                Http::response(['workflow_runs' => []], 200),
            'https://api.github.com/repos/kmjtechno/kmj-codebridge/actions/workflows/oneclick-stage.yml/dispatches' =>
                Http::response('', 204),
        ]);
        $owner = User::factory()->create();
        $result = app(CodeBridgeStageDispatcher::class)->request($owner);
        $this->assertSame('REQUEST_ACCEPTED_NOT_STAGE_PROOF', $result['status']);
        $this->assertSame(str_repeat('a', 40), $result['sha']);
        $this->assertDatabaseHas('operator_action_audits', [
            'actor_user_id' => $owner->id,
            'action' => 'codebridge.stage',
            'outcome' => 'queued',
        ]);
        Http::assertSent(fn ($request): bool =>
            $request->url() === 'https://api.github.com/repos/kmjtechno/kmj-codebridge/actions/workflows/oneclick-stage.yml/dispatches'
            && $request->method() === 'POST'
            && $request['ref'] === 'main'
        );
        $this->expectException(RuntimeException::class);
        app(CodeBridgeStageDispatcher::class)->request($owner);
    }

    public function test_active_exact_sha_workflow_prevents_duplicate_dispatch(): void
    {
        Http::fake([
            'https://api.github.com/repos/kmjtechno/kmj-codebridge/commits/main' =>
                Http::response(['sha' => str_repeat('b', 40)], 200),
            'https://api.github.com/repos/kmjtechno/kmj-codebridge/actions/workflows/oneclick-stage.yml/runs*' =>
                Http::response(['workflow_runs' => [
                    ['head_sha' => str_repeat('b', 40), 'status' => 'in_progress'],
                ]], 200),
        ]);
        $owner = User::factory()->create();
        $this->expectException(RuntimeException::class);
        app(CodeBridgeStageDispatcher::class)->request($owner);
    }

    public function test_stale_source_or_invalid_api_result_does_not_dispatch(): void
    {
        Http::fake([
            'https://api.github.com/repos/kmjtechno/kmj-codebridge/commits/main' =>
                Http::response(['sha' => 'main'], 200),
        ]);
        $owner = User::factory()->create();
        try {
            app(CodeBridgeStageDispatcher::class)->request($owner);
            $this->fail('Invalid source SHA must be refused.');
        } catch (RuntimeException) {
            $this->assertDatabaseCount('operator_action_audits', 0);
            Http::assertNotSent(fn ($request): bool => $request->method() === 'POST');
        }
    }
}
