<?php

declare(strict_types=1);

use App\Http\Controllers\NativeMailController;
use Illuminate\Support\Facades\Route;

/*
 * KMJ native mail — no Gmail connector, no arbitrary SMTP endpoint;\n * external submission is guarded through existing local Elite Postfix.
 * Only verified passkey Platform Owners and explicitly granted KMJ staff.
 * Staff membership is a separate owner-controlled allowlist, NOT a customer
 * organization membership or arbitrary login.
 */
Route::middleware(['auth', 'verified', 'password.confirm'])->group(function (): void {
    Route::get('{portal}/mail', [NativeMailController::class, 'index'])
        ->whereIn('portal', ['operator', 'team'])
        ->name('kmj-mail.index');
    Route::post('{portal}/mail/send', [NativeMailController::class, 'send'])
        ->whereIn('portal', ['operator', 'team'])
        ->middleware('throttle:6,1')
        ->name('kmj-mail.send');
    Route::post('{portal}/mail/send-external', [NativeMailController::class, 'sendExternal'])
        ->whereIn('portal', ['operator', 'team'])
        ->middleware('throttle:5,1')
        ->name('kmj-mail.send-external');

    Route::post('{portal}/mail/drafts', [NativeMailController::class, 'draft'])
        ->whereIn('portal', ['operator', 'team'])
        ->middleware('throttle:15,1')
        ->name('kmj-mail.draft');
    Route::post('{portal}/mail/drafts/{message}/send', [NativeMailController::class, 'sendDraft'])
        ->whereIn('portal', ['operator', 'team'])
        ->whereNumber('message')
        ->middleware('throttle:6,1')
        ->name('kmj-mail.draft-send');
    Route::post('{portal}/mail/messages/{message}/trash', [NativeMailController::class, 'trash'])
        ->whereIn('portal', ['operator', 'team'])
        ->whereNumber('message')
        ->middleware('throttle:20,1')
        ->name('kmj-mail.trash');
    Route::post('{portal}/mail/messages/{message}/restore', [NativeMailController::class, 'restore'])
        ->whereIn('portal', ['operator', 'team'])
        ->whereNumber('message')
        ->middleware('throttle:20,1')
        ->name('kmj-mail.restore');

    // Preview-only external transport retains a separate default-off gate.
    Route::post('{portal}/mail/preview', [NativeMailController::class, 'preview'])
        ->whereIn('portal', ['operator', 'team'])
        ->middleware('throttle:2,1')
        ->name('kmj-mail.preview');

    Route::post('operator/mail/staff', [NativeMailController::class, 'grantStaff'])
        ->middleware('throttle:6,1')
        ->name('kmj-mail.staff-grant');
    Route::post('operator/mail/staff/{userId}/sender-alias', [NativeMailController::class, 'setStaffSenderAlias'])
        ->whereNumber('userId')
        ->middleware('throttle:6,1')
        ->name('kmj-mail.staff-sender-alias');

    Route::post('operator/mail/staff/{userId}/revoke', [NativeMailController::class, 'revokeStaff'])
        ->whereNumber('userId')
        ->middleware('throttle:6,1')
        ->name('kmj-mail.staff-revoke');
});
