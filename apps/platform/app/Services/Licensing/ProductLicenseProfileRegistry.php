<?php

namespace App\Services\Licensing;

use App\Services\Commerce\CloudOSProductCatalog;
use App\Services\Commerce\KmjProductCatalog;

final class ProductLicenseProfileRegistry
{
    public const MAIN_PLATFORM_SANDBOX_SLUG = 'kmj-main-platform-sandbox';

    public const MAIN_PLATFORM_SANDBOX_CAPABILITY = 'sandbox.product.access';

    public const CALIBRATION_CAPABILITY = 'calibration.pro.access';

    public const GENERIC_PRODUCT_CAPABILITY = 'product.access';

    public function forSlug(string $slug): ?ProductLicenseProfile
    {
        return match ($slug) {
            CloudOSProductCatalog::SLUG => new ProductLicenseProfile(
                CloudOSProductCatalog::SLUG,
                CloudOSProductCatalog::CAPABILITY,
                ['active'],
            ),
            KmjProductCatalog::CALIBRATION_SLUG => new ProductLicenseProfile(
                KmjProductCatalog::CALIBRATION_SLUG,
                self::CALIBRATION_CAPABILITY,
                ['sandbox'],
            ),
            KmjProductCatalog::DESKTOP_COMMANDER_SLUG,
            KmjProductCatalog::FORGE_SLUG,
            KmjProductCatalog::CONNECT_SLUG,
            KmjProductCatalog::CLOUD_NEXUS_SLUG,
            KmjProductCatalog::AGENT_SLUG,
            KmjProductCatalog::CREATIVE_STUDIO_SLUG,
            KmjProductCatalog::CINEMA_PLATFORM_SLUG,
            KmjProductCatalog::DOME_360_SLUG,
            KmjProductCatalog::CINEMA_PLAYER_SLUG,
            KmjProductCatalog::LICENSING_HUB_SLUG => new ProductLicenseProfile(
                $slug,
                self::GENERIC_PRODUCT_CAPABILITY,
                ['active'],
            ),
            self::MAIN_PLATFORM_SANDBOX_SLUG => new ProductLicenseProfile(
                self::MAIN_PLATFORM_SANDBOX_SLUG,
                self::MAIN_PLATFORM_SANDBOX_CAPABILITY,
                ['sandbox'],
            ),
            default => null,
        };
    }
}
