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

    public const DESKTOP_COMMANDER_SLUG = 'kmj-desktop-commander';

    public const DESKTOP_COMMANDER_NAME = 'KMJ Desktop Commander';

    public const FORGE_SLUG = 'kmj-forge';

    public const FORGE_NAME = 'KMJ Forge';

    public const CONNECT_SLUG = 'kmj-connect';

    public const CONNECT_NAME = 'KMJ Connect';

    public const OMNIDESK_SLUG = 'kmj-omnidesk';

    public const OMNIDESK_NAME = 'KMJ OmniDesk';

    public const CODEBRIDGE_SLUG = 'kmj-codebridge';

    public const CODEBRIDGE_NAME = 'KMJ CodeBridge';

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

    public const IMMERSIVE_CINEMA_SUITE_SLUG = 'kmj-immersive-cinema-suite';

    public const IMMERSIVE_CINEMA_SUITE_NAME = 'KMJ Immersive Cinema Suite';

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

    public const DOME_360_SLUG = 'kmj-360-dome';

    public const DOME_360_NAME = 'KMJ 360 Dome';

    public const CINEMA_VARIANTS = ['5D', '7D', '9D', '12D', '14D', '16D', '5DX'];

    public const LEGACY_CINEMA_VARIANT_SLUGS = [
        'kmj-5d-cinema',
        'kmj-7d-cinema',
        'kmj-9d-cinema',
        'kmj-12d-cinema',
        'kmj-14d-cinema',
        'kmj-16d-cinema',
        'kmj-5dx-cinema',
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
            $cloudOS = $this->cloudOS->sync();

            $sandboxProducts = [
                self::CALIBRATION_SLUG => self::CALIBRATION_NAME,
                self::DESKTOP_COMMANDER_SLUG => self::DESKTOP_COMMANDER_NAME,
                self::FORGE_SLUG => self::FORGE_NAME,
                self::OMNIDESK_SLUG => self::OMNIDESK_NAME,
                self::CODEBRIDGE_SLUG => self::CODEBRIDGE_NAME,
                self::CONNECT_SLUG => self::CONNECT_NAME,
                self::CLOUD_NEXUS_SLUG => self::CLOUD_NEXUS_NAME,
                self::AGENT_SLUG => self::AGENT_NAME,
                self::CREATIVE_STUDIO_SLUG => self::CREATIVE_STUDIO_NAME,
                self::CINEMA_PLATFORM_SLUG => self::CINEMA_PLATFORM_NAME,
                self::DOME_SLUG => self::DOME_NAME,
                self::CINEMA_PLAYER_SLUG => self::CINEMA_PLAYER_NAME,
                self::IMMERSIVE_CINEMA_SUITE_SLUG => self::IMMERSIVE_CINEMA_SUITE_NAME,
                self::LICENSING_HUB_SLUG => self::LICENSING_HUB_NAME,
            ];

            $synced = [];

            foreach ($sandboxProducts as $slug => $name) {
                $product = $this->products->ensureSandboxProduct($slug, $name);
                $this->assertSandboxProduct($product, $slug, $name);
                $synced[$slug] = $product;
            }

            $catalog = [
                self::CLOUDOS_SLUG => $cloudOS,
                ...$synced,
            ];

            foreach ($catalog as $slug => $product) {
                $product->refresh();
                $this->seedManagementDefaults($product, $slug);
            }

            return $catalog;
        });
    }

    private function seedManagementDefaults(Product $product, string $slug): void
    {
        $attributes = $product->getAttributes();

        if (! array_key_exists('lifecycle', $attributes)) {
            return;
        }

        $untouched = (bool) $product->getAttribute('is_public') === false
            && (int) $product->getAttribute('sort_order') === 100
            && (string) $product->getAttribute('lifecycle') === 'planned'
            && $product->getAttribute('image_path') === null
            && $product->getAttribute('summary') === null
            && (bool) $product->getAttribute('purchase_enabled') === false
            && (bool) $product->getAttribute('licensing_enabled') === false;

        if (! $untouched) {
            return;
        }

        $defaults = match ($slug) {
            self::CLOUDOS_SLUG => ['available', 10, '/assets/products/kmj-cloudos.webp', true, true],
            self::CALIBRATION_SLUG => ['preview', 20, '/assets/products/kmj-calibration.webp', false, false],
            self::CINEMA_PLATFORM_SLUG => ['research', 30, '/assets/products/kmj-cinema-platform.webp', false, false],
            self::DOME_SLUG => ['research', 40, '/assets/products/kmj-360-dome.webp', false, false],
            self::IMMERSIVE_CINEMA_SUITE_SLUG => ['planned', 50, null, false, false],
            self::CINEMA_PLAYER_SLUG => ['research', 60, '/assets/products/kmj-cinema-player.webp', false, false],
            self::LICENSING_HUB_SLUG => ['research', 70, '/assets/products/kmj-licensing-hub.webp', false, true],
            self::FORGE_SLUG => ['research', 80, '/assets/products/kmj-forge.webp', false, false],
            self::OMNIDESK_SLUG => ['research', 85, null, false, true],
            self::CODEBRIDGE_SLUG => ['research', 87, null, false, true],
            self::DESKTOP_COMMANDER_SLUG => ['public-beta', 89, null, false, true],
            self::CONNECT_SLUG => ['planned', 90, '/assets/products/kmj-connect.webp', false, false],
            self::CLOUD_NEXUS_SLUG => ['research', 100, '/assets/products/kmj-cloud-nexus.webp', false, false],
            self::AGENT_SLUG => ['research', 110, '/assets/products/kmj-agent.webp', false, false],
            self::CREATIVE_STUDIO_SLUG => ['planned', 120, '/assets/products/kmj-creative-studio.webp', false, false],
            default => null,
        };

        if ($defaults === null) {
            return;
        }

        [$lifecycle, $sortOrder, $imagePath, $purchaseEnabled, $licensingEnabled] = $defaults;

        $product->forceFill([
            'lifecycle' => $lifecycle,
            'is_public' => true,
            'sort_order' => $sortOrder,
            'image_path' => $imagePath,
            'purchase_enabled' => $purchaseEnabled,
            'licensing_enabled' => $licensingEnabled,
        ])->save();
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
