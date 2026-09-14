<?php

use App\Http\Controllers\StagingMonitoringController;
use Illuminate\Support\Facades\Route;

Route::get('/info', [StagingMonitoringController::class, 'index'])
    ->name('staging.monitoring.index');

Route::get('/info/status', [StagingMonitoringController::class, 'status'])
    ->middleware('throttle:120,1')
    ->name('staging.monitoring.status');
