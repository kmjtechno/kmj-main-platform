<?php

declare(strict_types=1);

namespace Tests\Unit;

use App\Services\Licensing\CodeBridge\CodeBridgeLocalTelemetry;
use Illuminate\Support\Facades\Cache;
use Tests\TestCase;

final class CodeBridgeLocalTelemetryTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();
        config()->set('cache.default', 'array');
        Cache::flush();
    }

    public function test_missing_observations_are_unknown_not_faked_zero_or_online(): void
    {
        $store = new CodeBridgeLocalTelemetry;
        $snapshot = $store->snapshot('tenant-a', ['p720']);
        self::assertNull($snapshot['active_devices']);
        self::assertNull($snapshot['ollama']['reachable']);
        self::assertNull($snapshot['autopilot']['queued']);
        self::assertSame(0, $snapshot['ollama']['sampled_devices']);
        self::assertTrue($snapshot['autopilot']['partial']);
    }

    public function test_fresh_local_report_is_tenant_bound_and_never_contains_agent_token(): void
    {
        $store = new CodeBridgeLocalTelemetry;
        $store->record('tenant-a', 'p720', 'kmj-main-platform', [
            'ollama' => ['reachable' => true, 'models' => ['qwen3:4b']],
            'queue' => ['queued' => 2, 'running' => 1, 'waiting' => 0],
        ]);
        $own = $store->snapshot('tenant-a', ['p720']);
        self::assertSame(1, $own['active_devices']);
        self::assertSame(true, $own['ollama']['reachable']);
        self::assertSame(['qwen3:4b'], $own['ollama']['models']);
        self::assertSame(2, $own['autopilot']['queued']);
        self::assertFalse($own['autopilot']['partial']);
        self::assertStringNotContainsString('secret', json_encode($own, JSON_THROW_ON_ERROR));

        $foreign = $store->snapshot('tenant-b', ['p720']);
        self::assertNull($foreign['active_devices']);

        // A revoked/expired grant is excluded by caller-supplied active scope.
        $removed = $store->snapshot('tenant-a', []);
        self::assertSame(0, $removed['authorized_devices']);
        self::assertSame(0, $removed['active_devices']);
    }

    public function test_expired_and_future_dated_cache_reports_do_not_claim_devices_active(): void
    {
        $store = new CodeBridgeLocalTelemetry;
        $key = 'codebridge:local-telemetry:'.hash('sha256', "tenant-a\0p720");
        foreach ([time() - 91, time() + 120] as $timestamp) {
            Cache::put($key, [
                'device_id' => 'p720',
                'project_id' => 'kmj-main-platform',
                'reported_at_epoch' => $timestamp,
                'ollama' => ['reachable' => true, 'models' => ['qwen3:4b']],
                'queue' => ['queued' => 19, 'running' => 1, 'waiting' => 0],
            ], 120);
            $snapshot = $store->snapshot('tenant-a', ['p720']);
            self::assertNull($snapshot['active_devices']);
            self::assertNull($snapshot['autopilot']['queued']);
        }
    }

    public function test_unsampled_queue_is_null_not_zero(): void
    {
        $store = new CodeBridgeLocalTelemetry;
        $store->record('tenant-a', 'p720', 'kmj-main-platform', [
            'ollama' => ['reachable' => false, 'models' => []],
        ]);
        $snapshot = $store->snapshot('tenant-a', ['p720']);
        self::assertSame(1, $snapshot['active_devices']);
        self::assertFalse($snapshot['ollama']['reachable']);
        self::assertNull($snapshot['autopilot']['queued']);
    }
}
