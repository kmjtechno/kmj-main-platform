<?php

declare(strict_types=1);

use App\Http\Controllers\AiProviderController;
use App\Http\Controllers\HuggingFaceConnectController;
use Illuminate\Support\Facades\Route;

Route::prefix('services/kmj-codebridge/ai-providers')->name('ai-providers.')->group(function (): void {
    Route::get('/', [AiProviderController::class, 'index'])->name('index');
    Route::post('/', [AiProviderController::class, 'store'])->middleware(['password.confirm', 'throttle:20,1'])->name('store');
    Route::post('connect/kilo-free', [AiProviderController::class, 'connectKiloFree'])->middleware(['password.confirm', 'throttle:10,1'])->name('kilo-free.start');
    Route::post('connect/horde-anonymous', [AiProviderController::class, 'connectHordeAnonymous'])->middleware(['password.confirm', 'throttle:10,1'])->name('horde-anonymous.start');
    Route::post('connect/openrouter', [AiProviderController::class, 'connectOpenRouter'])->middleware(['password.confirm', 'throttle:10,1'])->name('openrouter.start');
    Route::get('connect/openrouter/callback', [AiProviderController::class, 'openRouterCallback'])->middleware('throttle:20,1')->name('openrouter.callback');
    Route::post('connect/huggingface', [HuggingFaceConnectController::class, 'start'])->middleware(['password.confirm', 'throttle:10,1'])->name('huggingface.start');
    Route::get('connect/huggingface/callback', [HuggingFaceConnectController::class, 'callback'])->middleware('throttle:20,1')->name('huggingface.callback');
    Route::patch('{provider}', [AiProviderController::class, 'update'])->middleware(['password.confirm', 'throttle:60,1'])->name('update');
    Route::post('{provider}/test', [AiProviderController::class, 'test'])->middleware('throttle:10,1')->name('test');
    Route::delete('{provider}', [AiProviderController::class, 'destroy'])->middleware(['password.confirm', 'throttle:20,1'])->name('destroy');
});
