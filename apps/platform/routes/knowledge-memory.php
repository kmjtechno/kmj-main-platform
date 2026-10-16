<?php

declare(strict_types=1);

use App\Http\Controllers\KnowledgeMemoryController;
use Illuminate\Support\Facades\Route;

// Included only in web.php's auth + verified group. Reads require existing
// membership + CodeBridge entitlement; writes also need owner status and
// recent password confirmation. Disabled by default via configuration.
Route::prefix('services/kmj-codebridge/knowledge-memory')
    ->name('knowledge-memory.')
    ->group(function (): void {
        Route::get('/', [KnowledgeMemoryController::class, 'index'])
            ->middleware('throttle:30,1')->name('index');
        Route::get('{observation}', [KnowledgeMemoryController::class, 'show'])
            ->whereUuid('observation')->middleware('throttle:30,1')->name('show');
        Route::post('/', [KnowledgeMemoryController::class, 'store'])
            ->middleware(['password.confirm', 'throttle:10,1'])->name('store');
    });
