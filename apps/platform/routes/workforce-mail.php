<?php

declare(strict_types=1);

use App\Http\Controllers\NativeMailAiController;
use App\Http\Controllers\NativeMailController;
use App\Http\Controllers\OwnerNativeSmtpController;
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
    // Explicit per-action user consent. No autonomous sending or provider override.
    Route::post('{portal}/mail/ai/generate', [NativeMailAiController::class, 'generate'])
        ->whereIn('portal', ['operator', 'team'])
        ->middleware('throttle:4,1')
        ->name('kmj-mail.ai-generate');

    // One authorized mailbox per request, max 40 IDs, no SMTP or irreversible delete.
    Route::post('{portal}/mail/messages/manage', [NativeMailController::class, 'manage'])
        ->whereIn('portal', ['operator', 'team'])
        ->middleware('throttle:20,1')
        ->name('kmj-mail.manage');
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

    Route::get('operator/mail/smtp', [OwnerNativeSmtpController::class, 'index'])
        ->name('kmj-mail.smtp-settings');
    Route::post('operator/mail/smtp/credentials', [OwnerNativeSmtpController::class, 'credentials'])
        ->middleware('throttle:3,10,kmj-native-smtp-credentials')
        ->name('kmj-mail.smtp-credentials');
    Route::post('operator/mail/smtp/theme', [OwnerNativeSmtpController::class, 'theme'])
        ->middleware('throttle:6,1,kmj-mail-theme')
        ->name('kmj-mail.enterprise-theme');
    Route::post('operator/mail/smtp/test', [OwnerNativeSmtpController::class, 'test'])
        ->middleware('throttle:2,1,kmj-native-smtp-test')
        ->name('kmj-mail.smtp-test');
    Route::post('operator/mail/smtp/activate', [OwnerNativeSmtpController::class, 'activate'])
        ->middleware('throttle:4,1,kmj-native-smtp-activate')
        ->name('kmj-mail.smtp-activate');
    Route::post('operator/mail/smtp/pause', [OwnerNativeSmtpController::class, 'pause'])
        ->middleware('throttle:4,1,kmj-native-smtp-pause')
        ->name('kmj-mail.smtp-pause');

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
