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

    public const CLOUD_NEXUS_SLUG = 'kmj-cloud-nexus';

    public const CLOUD_NEXUS_NAME = 'KMJ Cloud Nexus';

    public const FORGE_SLUG = 'kmj-forge';

    public const FORGE_NAME = 'KMJ Forge';

    public const AGENT_SLUG = 'kmj-agent';

    public const AGENT_NAME = 'KMJ Agent';

    public const CONNECT_SLUG = 'kmj-connect';

    public const CONNECT_NAME = 'KMJ Connect';

    private const SANDBOX_PRODUCTS = [
        self::CALIBRATION_SLUG => self::CALIBRATION_NAME,
        self::CLOUD_NEXUS_SLUG => self::CLOUD_NEXUS_NAME,
        self::FORGE_SLUG => self::FORGE_NAME,
        self::AGENT_SLUG => self::AGENT_NAME,
        self::CONNECT_SLUG => self::CONNECT_NAME,
    ];

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
            $catalog = [
                self::CLOUDOS_SLUG => $this->cloudOS->sync(),
            ];

            foreach (self::SANDBOX_PRODUCTS as $slug => $name) {
                $product = $this->products->ensureSandboxProduct($slug, $name);

                if (
                    (string) $product->getAttribute('name') !== $name
                    || (string) $product->getAttribute('status') !== 'sandbox'
                ) {
                    throw new DomainException(
                        sprintf('%s slug is already bound to conflicting catalog facts.', $name),
                    );
                }

                $catalog[$slug] = $product;
            }

            return $catalog;
        });
    }
}