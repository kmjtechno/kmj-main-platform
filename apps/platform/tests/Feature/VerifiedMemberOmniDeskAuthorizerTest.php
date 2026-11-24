<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use App\Services\Licensing\OmniDesk\OmniDeskApiAuthorizer;
use App\Services\Licensing\OmniDesk\VerifiedMemberOmniDeskAuthorizer;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Request;
use KMJ\MainPlatform\Organizations\Models\OrganizationMembership;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;
use Tests\TestCase;

final class VerifiedMemberOmniDeskAuthorizerTest extends TestCase
{
    use RefreshDatabase;

    private function requestFor(?User $user, ?string $headerOrganization = null, array $body = []): Request
    {
        $request = Request::create(
            '/api/v1/licensing/omnidesk/entitlements/current',
            'GET',
            $body,
        );
        if ($headerOrganization !== null) {
            $request->headers->set('X-KMJ-Organization-ID', $headerOrganization);
        }
        $request->setUserResolver(static fn (): ?User => $user);

        return $request;
    }

    public function test_unbound_authorizer_keeps_production_activation_fail_closed(): void
    {
        self::assertFalse(
            $this->app->bound(OmniDeskApiAuthorizer::class),
            'A concrete source class is not proof that the production auth guard is ready.',
        );
    }

    public function test_verified_owner_resolves_only_persisted_membership(): void
    {
        $owner = User::factory()->create();
        $organization = app(OrganizationCreator::class)->create('Owned OmniDesk Tenant', $owner->id);

        $principal = app(VerifiedMemberOmniDeskAuthorizer::class)->authorize(
            $this->requestFor($owner),
        );

        self::assertSame((string) $owner->getKey(), $principal->actorId);
        self::assertSame((string) $organization->getKey(), $principal->organizationId);
        self::assertTrue($principal->canManage);
    }

    public function test_unverified_user_is_not_a_valid_licensing_principal(): void
    {
        $user = User::factory()->unverified()->create();
        app(OrganizationCreator::class)->create('Unverified Tenant', $user->id);

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('OMNIDESK_UNAUTHENTICATED');

        app(VerifiedMemberOmniDeskAuthorizer::class)->authorize($this->requestFor($user));
    }

    public function test_anonymous_device_credentials_cannot_select_a_tenant(): void
    {
        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('OMNIDESK_UNAUTHENTICATED');

        app(VerifiedMemberOmniDeskAuthorizer::class)->authorize(
            $this->requestFor(null, 'client-selected-tenant'),
        );
    }

    public function test_foreign_organization_selector_is_rejected(): void
    {
        $owner = User::factory()->create();
        app(OrganizationCreator::class)->create('Owner Tenant', $owner->id);
        $foreign = User::factory()->create();
        $foreignOrg = app(OrganizationCreator::class)->create('Foreign Tenant', $foreign->id);

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('OMNIDESK_FORBIDDEN');

        app(VerifiedMemberOmniDeskAuthorizer::class)->authorize(
            $this->requestFor($owner, (string) $foreignOrg->getKey()),
        );
    }

    public function test_multiple_memberships_require_an_explicit_verified_selection(): void
    {
        $user = User::factory()->create();
        app(OrganizationCreator::class)->create('First Tenant', $user->id);
        $second = app(OrganizationCreator::class)->create('Second Tenant', $user->id);
        $authorizer = app(VerifiedMemberOmniDeskAuthorizer::class);

        try {
            $authorizer->authorize($this->requestFor($user));
            self::fail('Ambiguous multi-tenant context must not be selected implicitly.');
        } catch (DomainException $error) {
            self::assertSame('OMNIDESK_FORBIDDEN', $error->getMessage());
        }

        $principal = $authorizer->authorize(
            $this->requestFor($user, (string) $second->getKey()),
        );
        self::assertSame((string) $second->getKey(), $principal->organizationId);
    }

    public function test_untrusted_body_cannot_override_verified_organization(): void
    {
        $user = User::factory()->create();
        $owned = app(OrganizationCreator::class)->create('Real Membership', $user->id);
        $foreign = User::factory()->create();
        $foreignOrg = app(OrganizationCreator::class)->create('Injected Tenant', $foreign->id);

        $principal = app(VerifiedMemberOmniDeskAuthorizer::class)->authorize(
            $this->requestFor($user, null, ['organization_id' => (string) $foreignOrg->getKey()]),
        );
        self::assertSame((string) $owned->getKey(), $principal->organizationId);
    }

    public function test_member_can_read_own_scope_but_has_no_license_manage_right(): void
    {
        $user = User::factory()->create();
        $org = app(OrganizationCreator::class)->create('Member Tenant', $user->id);
        OrganizationMembership::query()
            ->where('user_id', $user->getKey())
            ->where('organization_id', $org->getKey())
            ->update(['role' => 'member']);

        $principal = app(VerifiedMemberOmniDeskAuthorizer::class)->authorize(
            $this->requestFor($user),
        );

        self::assertSame((string) $org->getKey(), $principal->organizationId);
        self::assertFalse($principal->canManage);
    }
}
