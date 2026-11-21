<?php

use App\Http\Controllers\ModelFabricController;
use Illuminate\Support\Facades\Route;

Route::middleware(['auth', 'verified', 'password.confirm'])
    ->prefix('operator/modelfabric')
    ->name('operator.modelfabric.')
    ->group(function (): void {
        Route::get('/', [ModelFabricController::class, 'index'])->name('index');
        Route::post('evidence', [ModelFabricController::class, 'storeEvidence'])->middleware('throttle:20,1')->name('evidence.store');
        Route::post('evidence/bulk', [ModelFabricController::class, 'bulkEvidence'])->middleware('throttle:10,1')->name('evidence.bulk');
        Route::post('evidence/{evidence}/renew', [ModelFabricController::class, 'renewEvidence'])->middleware('throttle:20,1')->name('evidence.renew');
        Route::delete('evidence/{evidence}', [ModelFabricController::class, 'revokeEvidence'])->middleware('throttle:20,1')->name('evidence.revoke');
        Route::patch('providers/{provider}', [ModelFabricController::class, 'updateProvider'])->middleware('throttle:20,1')->name('providers.update');
        Route::post('tokens', [ModelFabricController::class, 'storeToken'])->middleware('throttle:10,1')->name('tokens.store');
        Route::delete('tokens/{token}', [ModelFabricController::class, 'revokeToken'])->middleware('throttle:20,1')->name('tokens.revoke');
    });
