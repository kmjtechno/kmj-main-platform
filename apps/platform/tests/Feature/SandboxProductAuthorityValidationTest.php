<?php

namespace Tests\Feature;

use App\Services\Licensing\SandboxLicenseLifecycle;
use DateTimeImmutable;
use Illuminate\Foundation\Testing\RefreshDatabase;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Entitlements\Models\Entitlement;
use KMJ\MainPlatform\Entitlements\Models\EntitlementPolicy;
use KMJ\MainPlatform\Entitlements\Services\EntitlementIssuer;
use KMJ\MainPlatform\Organizations\Models\Organization;
use Tests\TestCase;

final class SandboxProductAuthorityValidationTest extends TestCase
{
    use RefreshDatabase;

    public function test_matching_active_product_and_entitlement_are_accepted(): void
    {
        [$organization, $product, $entitlement] = $this->authorityFixture();
        $licenses = app(SandboxLicenseLifecycle::class);

        $result = $licenses->validate($this->issue($licenses, $organization, $product, $entitlement));

        self::assertTrue($result['valid']);
        self::assertNull($result['reason']);
    }

    public function test_signed_license_is_rejected_when_authoritative_product_is_inactive(): void
    {
        [$organization, $product, $entitlement] = $this->authorityFixture();
        $licenses = app(SandboxLicenseLifecycle::class);
        $license = $this->issue($licenses, $organization, $product, $entitlement);

        $product->forceFill(['status' => 'inactive'])->save();

        $result = $licenses->validate($license);

        self::assertFalse($result['valid']);
        self::assertSame('product_unavailable', $result['reason']);
    }

    public function test_signed_license_is_rejected_when_authoritative_entitlement_is_revoked(): void
    {
        [$organization, $product, $entitlement] = $this->authorityFixture();
        $licenses = app(SandboxLicenseLifecycle::class);
        $license = $this->issue($licenses, $organization, $product, $entitlement);

        $entitlement->forceFill(['status' => 'revoked', 'ends_at' => now()])->save();

        $result = $licenses->validate($license);

        self::assertFalse($result['valid']);
        self::assertSame('entitlement_unavailable', $result['reason']);
    }

    public function test_signed_license_is_rejected_when_entitlement_no_longer_matches_product(): void
    {
        [$organization, $product, $entitlement] = $this->authorityFixture();
        $licenses = app(SandboxLicenseLifecycle::class);
        $license = $this->issue($licenses, $organization, $product, $entitlement);

        $otherProduct = Product::query()->create([
            'slug' => 'other-product',
            'name' => 'Other Product',
            'status' => 'sandbox',
        ]);
        $entitlement->forceFill(['product_id' => $otherProduct->getKey()])->save();

        $result = $licenses->validate($license);

        self::assertFalse($result['valid']);
        self::assertSame('entitlement_unavailable', $result['reason']);
    }

    private function issue(
        SandboxLicenseLifecycle $licenses,
        Organization $organization,
        Product $product,
        Entitlement $entitlement,
    ): string {
        return $licenses->issue(
            $organization->getKey(),
            $product->getKey(),
            $entitlement->getKey(),
            new DateTimeImmutable('+30 minutes'),
        );
    }

    /**
     * @return array{Organization, Product, Entitlement}
     */
    private function authorityFixture(): array
    {
        $organization = Organization::query()->create([
            'name' => 'KMJ Product Validation Lab',
        ]);
        $product = Product::query()->create([
            'slug' => 'product-validation-sandbox',
            'name' => 'Product Validation Sandbox',
            'status' => 'sandbox',
        ]);
        $policy = EntitlementPolicy::query()->create([
            'product_id' => $product->getKey(),
            'code' => 'product-validation-sandbox-use',
            'capability' => 'sandbox.use',
            'status' => 'active',
        ]);

        $entitlement = app(EntitlementIssuer::class)->issue(
            $organization->getKey(),
            $policy,
            'product-validation-entitlement',
        );

        return [$organization, $product, $entitlement];
    }
}
