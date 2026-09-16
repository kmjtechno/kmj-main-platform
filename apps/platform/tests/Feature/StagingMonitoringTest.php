<?php

namespace Tests\Feature;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Http;
use Inertia\Testing\AssertableInertia as Assert;
use Tests\TestCase;

final class StagingMonitoringTest extends TestCase
{
    use RefreshDatabase;

    public function test_monitor_is_hidden_outside_staging(): void
    {
        $this->get('/info')->assertNotFound();
        $this->getJson('/info/status')->assertNotFound();
    }

    public function test_monitor_is_available_on_exact_staging_host(): void
    {
        Http::fake([
            'http://127.0.0.1:20128/v1/models' => Http::response(['data' => []]),
        ]);

        // Symfony derives the Host from this absolute URI, overriding header-only values.
        $this->get('https://staging.kmjtechno.com/info')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('info-control')
                ->where('pollIntervalMs', 5000));

        $this->getJson('https://staging.kmjtechno.com/info/status')
            ->assertOk()
            ->assertJsonPath('runtime.application', true)
            ->assertJsonPath('runtime.database', true)
            ->assertJsonPath('safety.environment', 'staging');
    }

    public function test_monitor_is_hidden_on_production_hosts_even_in_staging_environment(): void
    {
        $originalEnvironment = app()->environment();
        Http::preventStrayRequests();

        try {
            foreach (['production', 'staging'] as $environment) {
                app()->detectEnvironment(static fn (): string => $environment);

                foreach (['kmjtechno.com', 'www.kmjtechno.com'] as $host) {
                    $this->get('https://'.$host.'/info')->assertNotFound();
                    $this->getJson('https://'.$host.'/info/status')->assertNotFound();
                }
            }
        } finally {
            app()->detectEnvironment(static fn (): string => $originalEnvironment);
        }
    }

    public function test_monitor_rejects_similar_hosts_and_untrusted_forwarded_host(): void
    {
        Http::preventStrayRequests();

        foreach (['staging.kmjtechno.com.example.test', 'other.kmjtechno.com'] as $host) {
            $this->get('https://'.$host.'/info')->assertNotFound();
            $this->getJson('https://'.$host.'/info/status')->assertNotFound();
        }

        $headers = ['X-Forwarded-Host' => 'staging.kmjtechno.com'];
        $this->get('https://kmjtechno.com/info', $headers)->assertNotFound();
        $this->getJson('https://kmjtechno.com/info/status', $headers)->assertNotFound();
    }

    public function test_staging_monitor_page_and_status_endpoint_are_available(): void
    {
        $originalEnvironment = app()->environment();
        app()->detectEnvironment(static fn (): string => 'staging');
        Http::fake([
            'http://127.0.0.1:20128/v1/models' => Http::response([
                'data' => [
                    ['id' => 'verified-free-one:free'],
                    ['id' => 'verified-free-two:free'],
                ],
            ]),
        ]);

        try {
            $this->get('/info')
                ->assertOk()
                ->assertInertia(fn (Assert $page) => $page
                    ->component('info-control')
                    ->where('pollIntervalMs', 5000));

            $response = $this->getJson('/info/status');
        } finally {
            app()->detectEnvironment(static fn (): string => $originalEnvironment);
        }

        $response
            ->assertOk()
            ->assertJsonPath('safety.environment', 'staging')
            ->assertJsonPath('safety.production_untouched', true)
            ->assertJsonPath('safety.paid_ai_fallback', 'prohibited')
            ->assertJsonPath('runtime.application', true)
            ->assertJsonPath('runtime.database', true)
            ->assertJsonPath('runtime.ai_router_online', true)
            ->assertJsonPath('runtime.ai_router_model_count', 2)
            ->assertJsonStructure([
                'status',
                'timestamp',
                'runtime' => [
                    'database_latency_ms',
                    'response_latency_ms',
                    'system_load_percent',
                    'memory_used_percent',
                    'disk_used_percent',
                    'server_uptime_seconds',
                    'pending_jobs',
                    'failed_jobs',
                    'runner_count',
                    'queue_worker_count',
                    'ai_router_latency_ms',
                ],
                'deployment',
                'delivery',
                'processes',
                'safety',
            ]);
    }

    public function test_recent_zero_cost_completion_is_visible_without_local_router(): void
    {
        Http::preventStrayRequests();
        $this->withCompletionEvidence([], function (): void {
            $this->getJson('https://staging.kmjtechno.com/info/status')
                ->assertOk()
                ->assertJsonPath('runtime.ai_router_online', true)
                ->assertJsonPath('runtime.ai_router_model_count', 1)
                ->assertJsonPath('runtime.ai_router_latency_ms', 25)
                ->assertJsonPath('processes.4.status', 'online');
        });
        Http::assertNothingSent();
    }

    public function test_invalid_or_stale_completion_cannot_report_online(): void
    {
        Http::fake(['*' => Http::response([], 503)]);
        foreach ([
            ['cost' => 1],
            ['cost' => false],
            ['cost' => null],
            ['verified_at' => now()->timestamp - 1801],
            ['verified_at' => now()->timestamp + 60],
            ['model' => 'unverified-model'],
            ['latency_ms' => -1],
        ] as $override) {
            $this->withCompletionEvidence($override, function (): void {
                $this->getJson('https://staging.kmjtechno.com/info/status')
                    ->assertOk()
                    ->assertJsonPath('runtime.ai_router_online', false)
                    ->assertJsonPath('runtime.ai_last_verified_at', null)
                    ->assertJsonPath('processes.4.status', 'blocked');
            });
        }
    }

    private function withCompletionEvidence(array $override, callable $assertions): void
    {
        $path = storage_path('app/monitoring/ai-worker.json');
        $previous = is_file($path) ? file_get_contents($path) : null;
        if (! is_dir(dirname($path))) {
            mkdir(dirname($path), 0755, true);
        }
        file_put_contents($path, json_encode(array_replace([
            'provider' => 'opencode-client',
            'model' => 'opencode/big-pickle',
            'status' => 'verified',
            'cost' => 0,
            'verified_at' => now()->timestamp,
            'latency_ms' => 25,
        ], $override)));

        try {
            $assertions();
        } finally {
            if ($previous === null) {
                unlink($path);
            } else {
                file_put_contents($path, $previous);
            }
        }
    }
}
