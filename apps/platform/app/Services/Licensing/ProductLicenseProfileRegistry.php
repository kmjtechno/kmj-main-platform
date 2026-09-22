<?php

namespace App\Services\Licensing;

use App\Services\Commerce\CloudOSProductCatalog;
use App\Services\Commerce\KmjProductCatalog;

final class ProductLicenseProfileRegistry
{
    public const MAIN_PLATFORM_SANDBOX_SLUG = 'kmj-main-platform-sandbox';

    public const MAIN_PLATFORM_SANDBOX_CAPABILITY = 'sandbox.product.access';

    public const CALIBRATION_CAPABILITY = 'calibration.pro.access';

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
            self::MAIN_PLATFORM_SANDBOX_SLUG => new ProductLicenseProfile(
                self::MAIN_PLATFORM_SANDBOX_SLUG,
                self::MAIN_PLATFORM_SANDBOX_CAPABILITY,
                ['sandbox'],
            ),
            default => null,
        };
    }
}
