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

    public const FORGE_SLUG = 'kmj-forge';

    public const FORGE_NAME = 'KMJ Forge';

    public const CONNECT_SLUG = 'kmj-connect';

    public const CONNECT_NAME = 'KMJ Connect';

    public const CLOUD_NEXUS_SLUG = 'kmj-cloud-nexus';

    public const CLOUD_NEXUS_NAME = 'KMJ Cloud Nexus';

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

            $sandboxProducts = [
                self::CALIBRATION_SLUG => self::CALIBRATION_NAME,
                self::FORGE_SLUG => self::FORGE_NAME,
                self::CONNECT_SLUG => self::CONNECT_NAME,
                self::CLOUD_NEXUS_SLUG => self::CLOUD_NEXUS_NAME,
            ];

            $synced = [];

            foreach ($sandboxProducts as $slug => $name) {
                $product = $this->products->ensureSandboxProduct($slug, $name);
                $this->assertSandboxProduct($product, $slug, $name);
                $synced[$slug] = $product;
            }

            return [
                self::CLOUDOS_SLUG => $cloudOS,
                ...$synced,
            ];
        });
    }

    private function assertSandboxProduct(
        Product $product,
        string $slug,
        string $name,
    ): void {
        if (
            (string) $product->getAttribute('slug') !== $slug
            || (string) $product->getAttribute('name') !== $name
            || (string) $product->getAttribute('status') !== 'sandbox'
        ) {
            throw new DomainException(
                sprintf('%s slug is already bound to conflicting catalog facts.', $name),
            );
        }
    }
}
