<?php

declare(strict_types=1);

use App\Models\OperatorActionAudit;
use App\Models\User;
use App\Notifications\WorkforceMailPreviewNotification;
use App\Services\Mail\RegistrationMailReadiness;
use App\Services\Mail\WorkforceMailCatalog;
use App\Services\PlatformOwnerAccess;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;
use Illuminate\Validation\ValidationException;
use Inertia\Inertia;
use KMJ\MainPlatform\Organizations\Models\OrganizationMembership;

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
        workforceMailPreviewToSelf($request, $user, 'owner');

        return redirect()->route('operator.mail.index')
            ->with('status', 'Test mail queued for processing. Inbox delivery is not yet confirmed.');
    })->middleware('throttle:2,1')->name('operator.mail.preview');

    Route::get('team/mail', function (Request $request) {
        $user = $request->user();
        abort_unless($user instanceof User, 401);
        abort_unless(workforceMailHasTeamMembership($user), 403);

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
        abort_unless(workforceMailHasTeamMembership($user), 403);
        workforceMailPreviewToSelf($request, $user, 'team');

        return redirect()->route('team.mail.index')
            ->with('status', 'Test mail queued for processing. Inbox delivery is not yet confirmed.');
    })->middleware('throttle:2,1')->name('team.mail.preview');
});

function workforceMailHasTeamMembership(User $user): bool
{
    // Organization membership is NOT proof of KMJ internal employment or
    // platform-owner authority; it only grants this account's own previews.
    return OrganizationMembership::query()
        ->where('user_id', (int) $user->getKey())
        ->whereIn('role', ['owner', 'admin', 'member'])
        ->exists();
}

function workforceMailPreviewToSelf(Request $request, User $user, string $audience): void
{
    $values = $request->validate([
        'kind' => ['required', 'string', 'max:80'],
    ]);
    $kind = (string) $values['kind'];

    $allowed = array_column(WorkforceMailCatalog::forAudience($audience), 'kind');
    if (! in_array($kind, $allowed, true)) {
        throw ValidationException::withMessages([
            'kind' => 'This preview is unavailable for your access level.',
        ]);
    }

    if (config('services.kmj_workforce_mail.preview_enabled', false) !== true
        || ! app(RegistrationMailReadiness::class)->canAttemptDelivery()) {
        throw ValidationException::withMessages([
            'kind' => 'Email preview delivery is disabled until an authorized mail readiness review.',
        ]);
    }

    // Never accept a client recipient, sender, URL, organization, or message
    // body. The only target is the verified current session account.
    $user->notify(new WorkforceMailPreviewNotification($kind, $audience));

    OperatorActionAudit::query()->create([
        'actor_user_id' => (int) $user->getKey(),
        'action' => 'workforce_mail_preview_requested',
        'outcome' => 'queued_not_delivered',
        'metadata' => ['audience' => $audience, 'kind' => $kind],
    ]);
}
