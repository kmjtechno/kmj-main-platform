<?php

declare(strict_types=1);

use App\Http\Controllers\AiProviderController;
use Illuminate\Support\Facades\Route;

Route::prefix('services/kmj-codebridge/ai-providers')->name('ai-providers.')->group(function (): void {
    Route::get('/', [AiProviderController::class, 'index'])->name('index');
    Route::post('/', [AiProviderController::class, 'store'])->middleware(['password.confirm', 'throttle:20,1'])->name('store');
    Route::patch('{provider}', [AiProviderController::class, 'update'])->middleware(['password.confirm', 'throttle:60,1'])->name('update');
    Route::post('{provider}/test', [AiProviderController::class, 'test'])->middleware('throttle:10,1')->name('test');
    Route::delete('{provider}', [AiProviderController::class, 'destroy'])->middleware(['password.confirm', 'throttle:20,1'])->name('destroy');
});
