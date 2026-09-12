<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use KMJ\MainPlatform\Organizations\Models\OrganizationMembership;
use KMJ\MainPlatform\Organizations\Services\OrganizationCapabilityContext;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;
use Tests\TestCase;

final class OrganizationCapabilityContextTest extends TestCase
{
    use RefreshDatabase;

    public function test_owner_capabilities_are_resolved_from_server_side_membership(): void
    {
        $user = User::factory()->create();
        $organization = app(OrganizationCreator::class)->create('Capability Lab', $user->id);
        $context = app(OrganizationCapabilityContext::class);

        self::assertTrue($context->allows($user->id, $organization->getKey(), 'organization.manage'));
        self::assertTrue($context->allows($user->id, $organization->getKey(), 'license.manage'));
        self::assertFalse($context->allows($user->id, $organization->getKey(), 'unknown.capability'));
    }

    public function test_non_member_is_denied_by_default(): void
    {
        $owner = User::factory()->create();
        $outsider = User::factory()->create();
        $organization = app(OrganizationCreator::class)->create('Private Lab', $owner->id);

        $context = app(OrganizationCapabilityContext::class);

        self::assertSame([], $context->capabilitiesFor($outsider->id, $organization->getKey()));
        self::assertFalse($context->allows($outsider->id, $organization->getKey(), 'organization.manage'));
    }

    public function test_unknown_membership_role_is_fail_closed(): void
    {
        $user = User::factory()->create();
        $organization = app(OrganizationCreator::class)->create('Role Lab', $user->id);

        OrganizationMembership::query()
            ->where('organization_id', $organization->getKey())
            ->where('user_id', $user->id)
            ->update(['role' => 'unexpected-role']);

        $context = app(OrganizationCapabilityContext::class);

        self::assertSame([], $context->capabilitiesFor($user->id, $organization->getKey()));
        self::assertFalse($context->allows($user->id, $organization->getKey(), 'license.manage'));
    }
}
