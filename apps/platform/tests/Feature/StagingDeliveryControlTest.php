<?php

namespace Tests\Feature;

use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

final class StagingDeliveryControlTest extends TestCase
{
    use RefreshDatabase;

    public function test_public_staging_status_exposes_sanitized_delivery_state_read_only(): void
    {
        $path = storage_path('framework/testing/staging-delivery-control.json');
        File::ensureDirectoryExists(dirname($path));
        File::put($path, json_encode([
            'version' => 1,
            'captured_at' => now()->toIso8601String(),
            'status' => 'active',
            'current_worker' => [
                'status' => 'in_progress',
                'run_number' => 108,
                'phase' => 'Run guarded worker cycle',
            ],
            'current_task' => [
                'issue_number' => 142,
                'title' => 'Accessibility fix',
                'state' => 'running',
            ],
            'pipeline' => [
                ['key' => 'worker', 'label' => 'AI Worker', 'status' => 'active'],
            ],
            'secret' => 'never-public',
        ], JSON_THROW_ON_ERROR));

        config([
            'kmj.ops.delivery_status_path' => $path,
            'kmj.ops.delivery_status_max_age_seconds' => 600,
        ]);
        Http::fake(['*' => Http::response([], 503)]);

        try {
            $response = $this->getJson('https://staging.kmjtechno.com/info/status');
        } finally {
            File::delete($path);
        }

        $response
            ->assertOk()
            ->assertJsonPath('delivery.status', 'active')
            ->assertJsonPath('delivery.current_worker.run_number', 108)
            ->assertJsonPath('delivery.current_task.issue_number', 142)
            ->assertJsonMissing(['secret' => 'never-public']);
    }
}
