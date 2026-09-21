<?php

namespace Tests\Feature;

use App\Services\Licensing\ProductLicenseProfileRegistry;
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

    public function test_matching_registered_product_and_entitlement_are_accepted(): void
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

    public function test_signed_license_is_rejected_when_entitlement_capability_does_not_match_profile(): void
    {
        [$organization, $product, $entitlement] = $this->authorityFixture();
        $licenses = app(SandboxLicenseLifecycle::class);
        $license = $this->issue($licenses, $organization, $product, $entitlement);

        $entitlement->forceFill(['capability' => 'wrong.capability'])->save();

        $result = $licenses->validate($license);

        self::assertFalse($result['valid']);
        self::assertSame('capability_mismatch', $result['reason']);
    }

    public function test_signed_license_is_rejected_for_unregistered_product(): void
    {
        $organization = Organization::query()->create(['name' => 'Unknown Product Lab']);
        $product = Product::query()->create([
            'slug' => 'unknown-product',
            'name' => 'Unknown Product',
            'status' => 'sandbox',
        ]);
        $policy = EntitlementPolicy::query()->create([
            'product_id' => $product->getKey(),
            'code' => 'unknown-product.default',
            'capability' => 'sandbox.product.access',
            'status' => 'active',
        ]);
        $entitlement = app(EntitlementIssuer::class)->issue(
            $organization->getKey(),
            $policy,
            'unknown-product-entitlement',
        );
        $licenses = app(SandboxLicenseLifecycle::class);

        $result = $licenses->validate(
            $this->issue($licenses, $organization, $product, $entitlement),
        );

        self::assertFalse($result['valid']);
        self::assertSame('unsupported_product', $result['reason']);
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
            'slug' => ProductLicenseProfileRegistry::MAIN_PLATFORM_SANDBOX_SLUG,
            'name' => 'KMJ Main Platform Sandbox',
            'status' => 'sandbox',
        ]);
        $policy = EntitlementPolicy::query()->create([
            'product_id' => $product->getKey(),
            'code' => 'main-platform.sandbox.default',
            'capability' => ProductLicenseProfileRegistry::MAIN_PLATFORM_SANDBOX_CAPABILITY,
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
