<?php

namespace App\Services\Commerce;

use DomainException;
use Illuminate\Support\Facades\DB;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Catalog\Services\ProductCatalog;

final class KmjProductCatalog
{
    public const CLOUDOS_SLUG = CloudOSProductCatalog::SLUG;

    public const CALIBRATION_SLUG = 'kmj-calibration-pro';

    public const CALIBRATION_NAME = 'KMJ Calibration Pro';

    public function __construct(
        private readonly CloudOSProductCatalog $cloudOS,
        private readonly ProductCatalog $products,
    ) {}

    /**
     * @return array<string, Product>
     */
    public function syncAll(): array
    {
        return DB::transaction(function (): array {
            $cloudOS = $this->cloudOS->sync();
            $calibration = $this->products->ensureSandboxProduct(
                self::CALIBRATION_SLUG,
                self::CALIBRATION_NAME,
            );

            if (
                (string) $calibration->getAttribute('name') !== self::CALIBRATION_NAME
                || (string) $calibration->getAttribute('status') !== 'sandbox'
            ) {
                throw new DomainException(
                    'Calibration Pro slug is already bound to conflicting catalog facts.',
                );
            }

            return [
                self::CLOUDOS_SLUG => $cloudOS,
                self::CALIBRATION_SLUG => $calibration,
            ];
        });
    }
}
