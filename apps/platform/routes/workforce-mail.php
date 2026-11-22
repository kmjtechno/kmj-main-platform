<?php

declare(strict_types=1);

use App\Models\User;
use App\Services\Mail\RegistrationMailReadiness;
use App\Services\Mail\WorkforceMailActions;
use App\Services\Mail\WorkforceMailCatalog;
use App\Services\PlatformOwnerAccess;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;
use Inertia\Inertia;

/*
 * Gmail-inspired, first-party template studio.
 * No Gmail OAuth, owner mailbox proxy, cross-tenant inbox, mass-send endpoint
 * or invented email data. Every sample is a self-addressed opt-in notification.
 */
Route::middleware(['auth', 'verified', 'password.confirm'])->group(function (): void {
    Route::get('operator/mail', function (Request $request, PlatformOwnerAccess $access) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);
        $access->require($user);

        return Inertia::render('mail-center', [
            'audience' => 'owner',
            'templates' => WorkforceMailCatalog::forAudience('owner'),
            'mailboxConnection' => 'not_connected',
            'transportCanAttempt' => app(RegistrationMailReadiness::class)->canAttemptDelivery(),
            'testEnabled' => config('services.kmj_workforce_mail.preview_enabled', false) === true,
        ]);
    })->name('operator.mail.index');

    Route::post('operator/mail/preview', function (Request $request, PlatformOwnerAccess $access) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);
        $access->require($user);
        app(WorkforceMailActions::class)->previewToSelf($request, $user, 'owner');

        return redirect()->route('operator.mail.index')
            ->with('status', 'Test mail queued for processing. Inbox delivery is not yet confirmed.');
    })->middleware('throttle:2,1')->name('operator.mail.preview');

    Route::get('team/mail', function (Request $request) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);
        abort_unless(app(WorkforceMailActions::class)->hasTeamMembership($user), 403);

        return Inertia::render('mail-center', [
            'audience' => 'team',
            'templates' => WorkforceMailCatalog::forAudience('team'),
            'mailboxConnection' => 'not_connected',
            'transportCanAttempt' => app(RegistrationMailReadiness::class)->canAttemptDelivery(),
            'testEnabled' => config('services.kmj_workforce_mail.preview_enabled', false) === true,
        ]);
    })->name('team.mail.index');

    Route::post('team/mail/preview', function (Request $request) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);
        abort_unless(app(WorkforceMailActions::class)->hasTeamMembership($user), 403);
        app(WorkforceMailActions::class)->previewToSelf($request, $user, 'team');

        return redirect()->route('team.mail.index')
            ->with('status', 'Test mail queued for processing. Inbox delivery is not yet confirmed.');
    })->middleware('throttle:2,1')->name('team.mail.preview');
});
