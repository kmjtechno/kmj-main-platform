<?php

use App\Models\OperatorActionAudit;
use App\Models\User;
use App\Services\DevForge\DevForgeBrokerClient;
use App\Services\PlatformOwnerAccess;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;
use Inertia\Inertia;

Route::middleware(['auth', 'verified', 'password.confirm'])
    ->prefix('operator/devforge')
    ->name('operator.devforge.')
    ->group(function (): void {
        Route::get('/', function (Request $request, PlatformOwnerAccess $access, DevForgeBrokerClient $broker) {
            $user = $request->user();
            abort_unless($user instanceof User, 401);
            $access->require($user);

            return Inertia::render('operator-devforge', [
                'devforge' => $broker->status(),
            ]);
        })->name('index');

        Route::post('actions', function (Request $request, PlatformOwnerAccess $access, DevForgeBrokerClient $broker) {
            $user = $request->user();
            abort_unless($user instanceof User, 401);
            $access->require($user);

            $validated = $request->validate([
                'action' => ['required', 'in:install,start,stop,restart'],
                'confirm' => ['required', 'in:CONTROL_KMJ_DEVFORGE'],
            ]);
            try {
                $broker->action($validated['action']);
            } catch (\RuntimeException $exception) {
                OperatorActionAudit::query()->create([
                    'actor_user_id' => $user->id,
                    'action' => 'devforge.'.$validated['action'],
                    'outcome' => 'failed',
                    'metadata' => ['reason' => 'BROKER_REJECTED'],
                ]);

                return back()->withErrors(['action' => $exception->getMessage()]);
            }

            OperatorActionAudit::query()->create([
                'actor_user_id' => $user->id,
                'action' => 'devforge.'.$validated['action'],
                'outcome' => 'accepted',
                'metadata' => ['execution' => 'asynchronous', 'health_verified' => false],
            ]);

            return redirect()->route('operator.devforge.index')
                ->with('status', 'DevForge action accepted. Await verified host status.');
        })->middleware('throttle:6,1')->name('actions');
    });
