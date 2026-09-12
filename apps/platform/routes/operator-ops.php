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

            $snapshot = $metrics->capture();

            return Inertia::render('operator-ops', [
                'snapshot' => $snapshot,
                'readiness' => $readiness->capture($snapshot),
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
