<?php

use App\Http\Controllers\ModelFabricApiController;
use App\Http\Middleware\AuthenticateModelFabricToken;
use Illuminate\Support\Facades\Route;

// OpenAI-compatible, bearer-token endpoint. IP throttle first so bad tokens cannot be brute forced.
Route::middleware(['throttle:120,1', AuthenticateModelFabricToken::class])
    ->prefix('modelfabric/v1')
    ->name('modelfabric.api.')
    ->group(function (): void {
        Route::get('models', [ModelFabricApiController::class, 'models'])->name('models');
        Route::post('chat/completions', [ModelFabricApiController::class, 'chat'])->name('chat');
    });
