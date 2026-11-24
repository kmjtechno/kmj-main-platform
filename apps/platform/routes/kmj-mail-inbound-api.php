<?php

declare(strict_types=1);

use App\Http\Controllers\NativeMailInboundPilotController;
use Illuminate\Support\Facades\Route;

// Stateless, signature-authenticated intake; defaults to disabled.
// No browser session, outbound SMTP, arbitrary recipient or MIME rendering.
Route::post('kmj-mail/inbound/pilot', NativeMailInboundPilotController::class)
    ->middleware('throttle:30,1,kmj-mail-inbound-pilot')
    ->name('kmj-mail.inbound-pilot');
