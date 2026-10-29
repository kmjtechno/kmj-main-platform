<?php

declare(strict_types=1);

use App\Http\Controllers\CodeBridgeWorkspaceController;
use Illuminate\Support\Facades\Route;

Route::get('services/kmj-codebridge/workspace', [CodeBridgeWorkspaceController::class, 'show'])
    ->middleware('throttle:60,1')
    ->name('codebridge.workspace');
