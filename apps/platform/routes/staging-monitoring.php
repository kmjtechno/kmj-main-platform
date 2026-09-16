<?php

use App\Http\Controllers\StagingDeliveryMonitoringController;
use Illuminate\Support\Facades\Route;

Route::get('/info', [StagingDeliveryMonitoringController::class, 'index'])
    ->name('staging.monitoring.index');

Route::get('/info/status', [StagingDeliveryMonitoringController::class, 'status'])
    ->middleware('throttle:120,1')
    ->name('staging.monitoring.status');
