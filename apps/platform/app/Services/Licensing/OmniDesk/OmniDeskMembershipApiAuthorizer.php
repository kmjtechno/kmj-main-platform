<?php

declare(strict_types=1);

namespace App\Services\Licensing\OmniDesk;

use DomainException;
use Illuminate\Http\Request;
use KMJ\MainPlatform\Organizations\Models\OrganizationMembership;
use KMJ\MainPlatform\Organizations\Services\OrganizationDirectory;

/**
 * Fail-closed tenant authorizer for the private OmniDesk API.
 *
 * It is deliberately NOT bound in any service provider: binding it is a
 * separate, owner-approved step (decision D2). Until then the routes keep
 * answering 503 SERVER_UNAVAILABLE.
 *
 * Every failure is an OMNIDESK_UNAUTHENTICATED / OMNIDESK_FORBIDDEN
 * DomainException. The tenant is never inferred: the caller must name it
 * explicitly and hold a membership row for exactly that organization.
 */
final class OmniDeskMembershipApiAuthorizer implements OmniDeskApiAuthorizer
{
    public const ORGANIZATION_HEADER = 'X-KMJ-Organization-Id';

    public function __construct(private readonly OrganizationDirectory $organizations) {}

    public function authorize(Request $request): OmniDeskApiPrincipal
    {
        $user = $request->user();
        $userId = $user?->getAuthIdentifier();
        if ($user === null || ! is_int($userId) || $userId < 1) {
            throw new DomainException('OMNIDESK_UNAUTHENTICATED');
        }

        $organizationId = $request->headers->get(self::ORGANIZATION_HEADER);
        if (! is_string($organizationId)
            || preg_match('/\A[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\z/i', $organizationId) !== 1) {
            throw new DomainException('OMNIDESK_FORBIDDEN');
        }
        $organizationId = strtolower($organizationId);

        $isMember = OrganizationMembership::query()
            ->where('organization_id', $organizationId)
            ->where('user_id', $userId)
            ->exists();
        if (! $isMember) {
            throw new DomainException('OMNIDESK_FORBIDDEN');
        }

        return new OmniDeskApiPrincipal(
            actorId: 'user:'.$userId,
            organizationId: $organizationId,
            canManage: $this->organizations->userCanManage($userId, $organizationId),
        );
    }
}
