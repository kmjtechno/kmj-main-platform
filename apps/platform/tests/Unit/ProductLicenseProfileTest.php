<?php

namespace Tests\Unit;

use App\Services\Commerce\CloudOSProductCatalog;
use App\Services\Commerce\KmjProductCatalog;
use App\Services\Licensing\ProductLicenseProfileRegistry;
use PHPUnit\Framework\TestCase;

final class ProductLicenseProfileTest extends TestCase
{
    public function test_cloudos_and_calibration_have_distinct_registered_capability_profiles(): void
    {
        $profiles = new ProductLicenseProfileRegistry;

        $cloudOS = $profiles->forSlug(CloudOSProductCatalog::SLUG);
        $calibration = $profiles->forSlug(KmjProductCatalog::CALIBRATION_SLUG);

        self::assertNotNull($cloudOS);
        self::assertNotNull($calibration);
        self::assertSame(CloudOSProductCatalog::CAPABILITY, $cloudOS->capability);
        self::assertSame(ProductLicenseProfileRegistry::CALIBRATION_CAPABILITY, $calibration->capability);
        self::assertNotSame($cloudOS->capability, $calibration->capability);
        self::assertTrue($cloudOS->allowsStatus('active'));
        self::assertFalse($cloudOS->allowsStatus('sandbox'));
        self::assertTrue($calibration->allowsStatus('sandbox'));
        self::assertFalse($calibration->allowsStatus('active'));
    }

    public function test_all_canonical_roadmap_products_have_active_only_main_platform_license_profiles(): void
    {
        $profiles = new ProductLicenseProfileRegistry;

        foreach ([
            KmjProductCatalog::FORGE_SLUG,
            KmjProductCatalog::CONNECT_SLUG,
            KmjProductCatalog::CLOUD_NEXUS_SLUG,
            KmjProductCatalog::AGENT_SLUG,
            KmjProductCatalog::CREATIVE_STUDIO_SLUG,
            KmjProductCatalog::CINEMA_PLATFORM_SLUG,
            KmjProductCatalog::DOME_360_SLUG,
            KmjProductCatalog::CINEMA_PLAYER_SLUG,
        ] as $slug) {
            $profile = $profiles->forSlug($slug);

            self::assertNotNull($profile);
            self::assertSame($slug, $profile->slug);
            self::assertSame(ProductLicenseProfileRegistry::GENERIC_PRODUCT_CAPABILITY, $profile->capability);
            self::assertTrue($profile->allowsStatus('active'));
            self::assertFalse($profile->allowsStatus('sandbox'));
        }
    }

    public function test_legacy_cinema_variant_slugs_are_not_independently_licensable(): void
    {
        $profiles = new ProductLicenseProfileRegistry;

        foreach (KmjProductCatalog::LEGACY_CINEMA_VARIANT_SLUGS as $slug) {
            self::assertNull($profiles->forSlug($slug));
        }
    }

    public function test_main_platform_sandbox_profile_remains_explicitly_registered(): void
    {
        $profile = (new ProductLicenseProfileRegistry)
            ->forSlug(ProductLicenseProfileRegistry::MAIN_PLATFORM_SANDBOX_SLUG);

        self::assertNotNull($profile);
        self::assertSame(
            ProductLicenseProfileRegistry::MAIN_PLATFORM_SANDBOX_CAPABILITY,
            $profile->capability,
        );
        self::assertTrue($profile->allowsStatus('sandbox'));
    }

    public function test_unknown_product_has_no_license_profile(): void
    {
        self::assertNull((new ProductLicenseProfileRegistry)->forSlug('unknown-product'));
    }
}
