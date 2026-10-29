<?php

declare(strict_types=1);

use App\Http\Controllers\CodeBridgeWorkspaceController;
use Illuminate\Support\Facades\Route;

Route::get('services/kmj-codebridge/workspace', [CodeBridgeWorkspaceController::class, 'show'])
    ->middleware('throttle:60,1')
    ->name('codebridge.workspace');

Route::prefix('services/kmj-codebridge/workspace')->name('codebridge.workspace.')->group(function (): void {
    Route::post('conversations', [CodeBridgeWorkspaceController::class, 'start'])->middleware('throttle:30,1')->name('start');
    Route::post('conversations/{conversation}/messages', [CodeBridgeWorkspaceController::class, 'send'])
        ->whereUuid('conversation')->middleware('throttle:20,1')->name('send');
    Route::post('conversations/{conversation}/messages/{message}/retry', [CodeBridgeWorkspaceController::class, 'retry'])
        ->whereUuid('conversation')->whereUlid('message')->middleware('throttle:20,1')->name('retry');
    Route::post('conversations/{conversation}/messages/{message}/cancel', [CodeBridgeWorkspaceController::class, 'cancel'])
        ->whereUuid('conversation')->whereUlid('message')->middleware('throttle:30,1')->name('cancel');
});
