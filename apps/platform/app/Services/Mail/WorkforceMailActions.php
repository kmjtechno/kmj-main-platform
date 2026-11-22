<?php

namespace App\Services\Mail;

use App\Models\OperatorActionAudit;
use App\Models\User;
use App\Notifications\WorkforceMailPreviewNotification;
use Illuminate\Http\Request;
use Illuminate\Validation\ValidationException;
use KMJ\MainPlatform\Organizations\Models\OrganizationMembership;

/**
 * Request-scoped, reentrant workforce mail authorization.
 *
 * Never trust client-selected recipients or organizations. Preview messages
 * are explicitly marked tests and can only go to the current verified user.
 */
final class WorkforceMailActions
{
    public function hasTeamMembership(User $user): bool
    {
        return OrganizationMembership::query()
            ->where('user_id', (int) $user->getKey())
            ->whereIn('role', ['owner', 'admin', 'member'])
            ->exists();
    }

    public function previewToSelf(Request $request, User $user, string $audience): void
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

        // No client recipient, from, URL, org scope or body. The only target
        // is the verified session user, after its route policy has passed.
        $user->notify(new WorkforceMailPreviewNotification($kind, $audience));

        OperatorActionAudit::query()->create([
            'actor_user_id' => (int) $user->getKey(),
            'action' => 'workforce_mail_preview_requested',
            'outcome' => 'queued_not_delivered',
            'metadata' => ['audience' => $audience, 'kind' => $kind],
        ]);
    }
}
