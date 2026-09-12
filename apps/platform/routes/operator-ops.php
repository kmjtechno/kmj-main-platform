<?php

use App\Models\OperatorActionAudit;
use App\Models\User;
use App\Services\Operations\OperationalReadinessSnapshot;
use App\Services\Operations\OperatorActionRunner;
use App\Services\Operations\ServerMetricsSnapshot;
use App\Services\PlatformOwnerAccess;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;
use Inertia\Inertia;

Route::middleware(['auth', 'verified', 'password.confirm'])
    ->prefix('operator')
    ->name('operator.')
    ->group(function (): void {
        Route::get('ops', function (
            Request $request,
            PlatformOwnerAccess $access,
            ServerMetricsSnapshot $metrics,
            OperationalReadinessSnapshot $readiness,
        ) {
            $user = $request->user();
            abort_unless($user instanceof User, 401);
            $access->require($user);

            try {
                $recentActions = OperatorActionAudit::query()
                    ->latest('id')
                    ->limit(20)
                    ->get(['id', 'actor_user_id', 'action', 'outcome', 'created_at'])
                    ->map(fn (OperatorActionAudit $event): array => [
                        'id' => $event->getKey(),
                        'actor_user_id' => $event->getAttribute('actor_user_id'),
                        'action' => $event->getAttribute('action'),
                        'outcome' => $event->getAttribute('outcome'),
                        'created_at' => $event->getAttribute('created_at')?->toISOString(),
                    ])
                    ->all();
            } catch (Throwable $exception) {
                report($exception);
                $recentActions = [];
            }

            try {
                $snapshot = $metrics->capture();
            } catch (Throwable $exception) {
                report($exception);
                $snapshot = [
                    'captured_at' => now()->toIso8601String(),
                    'environment' => app()->environment(),
                    'deployed_sha' => null,
                    'cpu' => [
                        'cores' => 0,
                        'load_1m' => 0.0,
                        'load_5m' => 0.0,
                        'load_15m' => 0.0,
                        'load_percent_estimate' => 0.0,
                    ],
                    'memory' => [
                        'total_bytes' => 0,
                        'used_bytes' => 0,
                        'available_bytes' => 0,
                        'used_percent' => 0.0,
                    ],
                    'disk' => [
                        'total_bytes' => 0,
                        'used_bytes' => 0,
                        'free_bytes' => 0,
                        'used_percent' => 0.0,
                    ],
                    'uptime_seconds' => null,
                    'php' => [
                        'memory_usage_bytes' => memory_get_usage(true),
                        'memory_peak_bytes' => memory_get_peak_usage(true),
                        'memory_limit' => (string) ini_get('memory_limit'),
                    ],
                    'database' => ['status' => 'degraded'],
                    'failed_jobs' => 0,
                    'queue_restart_at' => null,
                ];
            }

            try {
                $readinessSnapshot = $readiness->capture($snapshot);
            } catch (Throwable $exception) {
                report($exception);
                $missingBackup = [
                    'status' => 'unavailable',
                    'completed_at' => null,
                    'age_hours' => null,
                    'max_age_hours' => 0,
                    'git_sha' => null,
                ];
                $readinessSnapshot = [
                    'deployment' => [
                        'status' => 'degraded',
                        'deployed_sha' => $snapshot['deployed_sha'] ?? null,
                        'database_status' => $snapshot['database']['status'] ?? 'unknown',
                        'evidence' => 'runtime_probe_failed',
                    ],
                    'backups' => [
                        'daily' => $missingBackup,
                        'weekly' => $missingBackup,
                        'monthly' => $missingBackup,
                    ],
                    'autonomous_worker' => [
                        'status' => 'external_unobserved',
                        'source' => 'github_actions',
                        'execution_gate' => 'unknown',
                        'write_gate' => 'unknown',
                        'live_run_observed' => false,
                    ],
                    'free_ai_router' => [
                        'status' => 'unavailable',
                        'policy' => 'verified_zero_only',
                        'configured_provider_count' => 0,
                        'configured_providers' => [],
                        'live_route_observed' => false,
                        'paid_fallback' => false,
                    ],
                    'compliance_guard' => [
                        'status' => 'degraded',
                        'mode' => 'fail_closed',
                        'provider_policy_enforcement' => 'not_enabled',
                        'legal_interpretation' => false,
                        'signals' => [],
                    ],
                ];
            }

            return Inertia::render('operator-ops', [
                'snapshot' => $snapshot,
                'readiness' => $readinessSnapshot,
                'recentActions' => $recentActions,
            ]);
        })->name('ops.index');

        Route::post('ops/actions/queue-restart', function (
            Request $request,
            PlatformOwnerAccess $access,
            OperatorActionRunner $actions,
        ) {
            $user = $request->user();
            abort_unless($user instanceof User, 401);
            $access->require($user);
            $actions->restartQueueWorkers($user);

            return redirect()->route('operator.ops.index');
        })->name('ops.queue-restart');
    });
