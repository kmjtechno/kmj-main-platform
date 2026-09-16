<?php

use App\Http\Controllers\StagingDeliveryMonitoringController;
use App\Services\Staging\ProductionHomeMirror;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;

Route::get('/info', [StagingDeliveryMonitoringController::class, 'index'])
    ->name('staging.monitoring.index');

Route::get('/info/status', [StagingDeliveryMonitoringController::class, 'status'])
    ->middleware('throttle:120,1')
    ->name('staging.monitoring.status');

Route::get('/{path}', function (Request $request, ProductionHomeMirror $mirror) {
    abort_unless($mirror->shouldMirror($request), 404);

    try {
        return response($mirror->renderPath('/'.$request->route('path')), 200, [
            'Content-Type' => 'text/html; charset=UTF-8',
            'Cache-Control' => 'no-cache, private',
            'X-Robots-Tag' => 'noindex, nofollow',
        ]);
    } catch (RuntimeException) {
        return response('Production site mirror is temporarily unavailable.', 503);
    }
})->where('path', '.*')->name('staging.production-site.fallback');
