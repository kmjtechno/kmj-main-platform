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

    public const AGENT_SLUG = 'kmj-agent';

    public const AGENT_NAME = 'KMJ Agent';

    public const CREATIVE_STUDIO_SLUG = 'kmj-creative-studio';

    public const CREATIVE_STUDIO_NAME = 'KMJ Creative Studio';

    public const CINEMA_PLATFORM_SLUG = 'kmj-cinema-platform';

    public const DOME_SLUG = 'kmj-360-dome';
    public const DOME_NAME = 'KMJ 360 Dome';

    public const CINEMA_PLAYER_SLUG = 'kmj-cinema-player';
    public const CINEMA_PLAYER_NAME = 'KMJ Cinema Player';

    public const LICENSING_HUB_SLUG = 'kmj-licensing-hub';
    public const LICENSING_HUB_NAME = 'KMJ Licensing Hub';

    // Focused SaaS roadmap: shared AI foundation, distinct customer outcomes.
    public const AI_SUPPORT_SLUG = 'kmj-ai-support';
    public const AI_SUPPORT_NAME = 'KMJ AI Support';

    public const AUTOMATE_SLUG = 'kmj-automate';
    public const AUTOMATE_NAME = 'KMJ Automate';

    public const AI_GATEWAY_SLUG = 'kmj-ai-gateway';
    public const AI_GATEWAY_NAME = 'KMJ AI Gateway';

    public const CINEMA_PLATFORM_NAME = 'KMJ Cinema Platform';

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
                self::AGENT_SLUG => self::AGENT_NAME,
                self::CREATIVE_STUDIO_SLUG => self::CREATIVE_STUDIO_NAME,
                self::CINEMA_PLATFORM_SLUG => self::CINEMA_PLATFORM_NAME,
                self::DOME_SLUG => self::DOME_NAME,
                self::CINEMA_PLAYER_SLUG => self::CINEMA_PLAYER_NAME,
                self::LICENSING_HUB_SLUG => self::LICENSING_HUB_NAME,
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
