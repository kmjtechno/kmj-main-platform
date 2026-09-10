<?php

namespace Tests\Feature;

use App\Models\User;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use KMJ\MainPlatform\Catalog\Services\ProductCatalog;
use KMJ\MainPlatform\Entitlements\Models\EntitlementPolicy;
use KMJ\MainPlatform\Entitlements\Services\EntitlementIssuer;
use KMJ\MainPlatform\Entitlements\Services\EntitlementPolicyRegistry;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;
use Tests\TestCase;

final class AuthorityCoreTest extends TestCase
{
    use RefreshDatabase;

    public function test_organization_product_and_entitlement_form_an_idempotent_authority_chain(): void
    {
        $user = User::factory()->create();

        $organization = app(OrganizationCreator::class)->create('KMJ Sandbox Organization', $user->id);
        $product = app(ProductCatalog::class)->ensureSandboxProduct('kmj-sandbox', 'KMJ Sandbox Product');
        $policy = app(EntitlementPolicyRegistry::class)->ensure(
            $product->getKey(),
            'sandbox.default',
            'sandbox.product.access',
        );

        $issuer = app(EntitlementIssuer::class);
        $first = $issuer->issue($organization->getKey(), $policy, 'test-request-001');
        $retry = $issuer->issue($organization->getKey(), $policy, 'test-request-001');

        $this->assertSame($first->getKey(), $retry->getKey());
        $this->assertDatabaseHas('organization_memberships', [
            'organization_id' => $organization->getKey(),
            'user_id' => $user->id,
            'role' => 'owner',
        ]);
        $this->assertDatabaseHas('entitlements', [
            'id' => $first->getKey(),
            'organization_id' => $organization->getKey(),
            'product_id' => $product->getKey(),
            'policy_id' => $policy->getKey(),
            'capability' => 'sandbox.product.access',
            'status' => 'active',
        ]);
        $this->assertDatabaseCount('entitlement_ledger', 1);
        $this->assertDatabaseHas('entitlement_ledger', [
            'entitlement_id' => $first->getKey(),
            'organization_id' => $organization->getKey(),
            'event_type' => 'entitlement.issued',
        ]);
    }

    public function test_inactive_policy_cannot_issue_an_entitlement(): void
    {
        $user = User::factory()->create();
        $organization = app(OrganizationCreator::class)->create('Blocked Organization', $user->id);
        $product = app(ProductCatalog::class)->ensureSandboxProduct('blocked-sandbox', 'Blocked Sandbox');

        $policy = EntitlementPolicy::query()->create([
            'product_id' => $product->getKey(),
            'code' => 'sandbox.blocked',
            'capability' => 'sandbox.product.access',
            'status' => 'disabled',
        ]);

        $this->expectException(DomainException::class);

        app(EntitlementIssuer::class)->issue($organization->getKey(), $policy, 'test-request-blocked');
    }
}
