<?php

declare(strict_types=1);

namespace App\Services\Licensing\OmniDesk;

use App\Models\User;
use DomainException;
use Illuminate\Http\Request;
use KMJ\MainPlatform\Organizations\Services\OrganizationCapabilityContext;
use KMJ\MainPlatform\Organizations\Services\OrganizationDirectory;

/**
 * Concrete, tenant-bound principal resolver for an already authenticated
 * first-party user. Source-only: intentionally NOT registered in the Laravel
 * container until the production authentication/step-up policy is reviewed.
 *
 * No body/query tenant ID, device ID or bearer claim can grant authority.
 * An optional organization header only selects one of the user's actual
 * server-side memberships. Ambiguous multi-org requests fail closed.
 */
final class VerifiedMemberOmniDeskAuthorizer implements OmniDeskApiAuthorizer
{
    public function __construct(
        private readonly OrganizationDirectory $organizations,
        private readonly OrganizationCapabilityContext $capabilities,
    ) {}

    public function authorize(Request $request): OmniDeskApiPrincipal
    {
        $user = $request->user();
        if (! $user instanceof User || ! $user->hasVerifiedEmail()) {
            throw new DomainException('OMNIDESK_UNAUTHENTICATED');
        }

        $userId = (int) $user->getKey();
        if ($userId <= 0) {
            throw new DomainException('OMNIDESK_UNAUTHENTICATED');
        }

        $memberships = $this->organizations->forUser($userId);
        $requested = $request->header('X-KMJ-Organization-ID');

        if ($requested === null) {
            // Never guess a tenant for a user who belongs to several.
            if (count($memberships) !== 1) {
                throw new DomainException('OMNIDESK_FORBIDDEN');
            }

            $organizationId = $memberships[0]['id'];
        } else {
            if (! is_string($requested) || trim($requested) === '') {
                throw new DomainException('OMNIDESK_FORBIDDEN');
            }

            $matched = array_values(array_filter(
                $memberships,
                static fn (array $membership): bool => $membership['id'] === $requested,
            ));
            if (count($matched) !== 1) {
                throw new DomainException('OMNIDESK_FORBIDDEN');
            }

            $organizationId = $matched[0]['id'];
        }

        // Only the established license.manage capability grants write
        // operations. Members may read tenant-scoped status, never activate,
        // renew, transfer, or deactivate someone else's license.
        return new OmniDeskApiPrincipal(
            actorId: (string) $userId,
            organizationId: $organizationId,
            canManage: $this->capabilities->allows($userId, $organizationId, 'license.manage'),
        );
    }
}
