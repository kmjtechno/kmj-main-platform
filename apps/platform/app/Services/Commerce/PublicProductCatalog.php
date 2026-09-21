<?php

namespace App\Services\Commerce;

use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Entitlements\Models\EntitlementPolicy;

final class PublicProductCatalog
{
    /**
     * @return array<int, array<string, mixed>>
     */
    public function all(): array
    {
        $products = Product::query()
            ->whereIn('slug', [
                CloudOSProductCatalog::SLUG,
                KmjProductCatalog::CALIBRATION_SLUG,
            ])
            ->get()
            ->keyBy('slug');

        return collect([
            CloudOSProductCatalog::SLUG,
            KmjProductCatalog::CALIBRATION_SLUG,
        ])
            ->map(fn (string $slug): ?array => $this->present($products->get($slug)))
            ->filter()
            ->values()
            ->all();
    }

    /**
     * @return array<string, mixed>|null
     */
    public function find(string $slug): ?array
    {
        if (! in_array($slug, [
            CloudOSProductCatalog::SLUG,
            KmjProductCatalog::CALIBRATION_SLUG,
        ], true)) {
            return null;
        }

        return $this->present(Product::query()->where('slug', $slug)->first());
    }

    /**
     * @return array<string, mixed>|null
     */
    private function present(?Product $product): ?array
    {
        if ($product === null) {
            return null;
        }

        return match ((string) $product->getAttribute('slug')) {
            CloudOSProductCatalog::SLUG => $this->cloudOS($product),
            KmjProductCatalog::CALIBRATION_SLUG => $this->calibration(),
            default => null,
        };
    }

    /**
     * @return array<string, mixed>
     */
    private function cloudOS(Product $product): array
    {
        $purchaseEnabled = (string) $product->getAttribute('status') === 'active'
            && EntitlementPolicy::query()
                ->where('product_id', $product->getKey())
                ->where('code', CloudOSProductCatalog::POLICY_CODE)
                ->where('capability', CloudOSProductCatalog::CAPABILITY)
                ->where('status', 'active')
                ->exists();

        return [
            'slug' => CloudOSProductCatalog::SLUG,
            'name' => CloudOSProductCatalog::NAME,
            'lifecycle' => $purchaseEnabled ? 'active' : 'unavailable',
            'lifecycle_label' => $purchaseEnabled ? 'Commercial catalog' : 'Unavailable',
            'purchase_enabled' => $purchaseEnabled,
            'eyebrow' => 'Cloud operating platform',
            'headline' => 'Explore the governed CloudOS operating workflow before requesting access.',
            'summary' => 'KMJ CloudOS is the canonical cloud product in Main Platform. Product access is governed through organization, purchase, entitlement and licensing authority rather than browser state.',
            'truth' => [
                'status' => $purchaseEnabled
                    ? 'Active canonical catalog product with Main Platform entitlement authority.'
                    : 'Commercial access is unavailable until canonical product and policy authority are active.',
            ],
            'proof' => [
                [
                    'title' => 'Canonical product authority',
                    'detail' => 'The Main Platform catalog binds the kmj-cloudos slug to the governed commercial product.',
                    'state' => 'repository-verified',
                ],
                [
                    'title' => 'Entitlement boundary',
                    'detail' => 'Access uses the cloudos.platform.access capability and remains separate from payment confirmation.',
                    'state' => 'repository-verified',
                ],
                [
                    'title' => 'Safe virtual workflow',
                    'detail' => 'The browser demo uses deterministic sample events and never controls live infrastructure.',
                    'state' => 'simulation',
                ],
            ],
            'evidence' => [
                [
                    'criterion' => 'Lifecycle',
                    'value' => $purchaseEnabled ? 'Commercial catalog active' : 'Commercial catalog unavailable',
                    'state' => 'verified',
                    'evidence_ref' => 'Canonical product status + CloudOS entitlement policy',
                ],
                [
                    'criterion' => 'Purchase boundary',
                    'value' => $purchaseEnabled
                        ? 'Request access only; purchase or payment confirmation does not grant entitlement.'
                        : 'Ordering disabled.',
                    'state' => 'verified',
                    'evidence_ref' => 'Main Platform purchase and fulfillment authority',
                ],
                [
                    'criterion' => 'License authority',
                    'value' => 'Organization, product and active entitlement remain server-authoritative.',
                    'state' => 'verified',
                    'evidence_ref' => 'Main Platform entitlement and license authority',
                ],
                [
                    'criterion' => 'Demo boundary',
                    'value' => 'Deterministic browser simulation with no live infrastructure mutation.',
                    'state' => 'verified',
                    'evidence_ref' => 'Public Product Hub simulation contract',
                ],
            ],
            'trust' => [
                'purchase_boundary' => $purchaseEnabled ? 'request-only' : 'disabled',
                'demo_boundary' => 'simulation-only',
                'license_authority' => 'server-authoritative',
                'production_signing' => 'owner-gated-out-of-scope',
            ],
            'demo' => [
                'kind' => 'cloudos',
                'simulation' => true,
                'label' => 'Interactive workflow simulation',
                'steps' => [
                    ['key' => 'monitor', 'label' => 'Monitor', 'detail' => 'Inspect a seeded service-health snapshot.'],
                    ['key' => 'validate', 'label' => 'Validate', 'detail' => 'Review deterministic readiness checks.'],
                    ['key' => 'deploy', 'label' => 'Deploy', 'detail' => 'Preview an isolated simulated deployment transition.'],
                    ['key' => 'verify', 'label' => 'Verify', 'detail' => 'Confirm a synthetic post-deploy state and rollback boundary.'],
                ],
            ],
            'cta' => [
                'primary' => 'Launch virtual demo',
                'secondary' => $purchaseEnabled ? 'Request access' : 'Unavailable',
            ],
        ];
    }

    /**
     * @return array<string, mixed>
     */
    private function calibration(): array
    {
        return [
            'slug' => KmjProductCatalog::CALIBRATION_SLUG,
            'name' => KmjProductCatalog::CALIBRATION_NAME,
            'lifecycle' => 'development-preview',
            'lifecycle_label' => 'Development preview',
            'purchase_enabled' => false,
            'eyebrow' => 'Projector + camera calibration',
            'headline' => 'See the complete calibration workflow before touching hardware.',
            'summary' => 'A guided projector-camera calibration experience being built around a native C++ foundation, deterministic verification and fail-closed runtime behavior.',
            'truth' => [
                'physical_capability_certified' => false,
                'status' => 'Buildable C++ foundation; physical calibration capability is not yet certified.',
            ],
            'proof' => [
                [
                    'title' => 'Native C++ foundation',
                    'detail' => 'C++23, CMake and Ninja foundation with Debug and Release verification.',
                    'state' => 'repository-verified',
                ],
                [
                    'title' => 'Fail-closed behavior',
                    'detail' => 'Calibration, warp and storage placeholders refuse to claim success until implemented.',
                    'state' => 'repository-verified',
                ],
                [
                    'title' => 'Guided product experience',
                    'detail' => 'The public demo explains the intended Setup → Capture → Analyze → Results flow without claiming physical output.',
                    'state' => 'simulation',
                ],
            ],
            'evidence' => [
                [
                    'criterion' => 'Lifecycle',
                    'value' => 'Development preview',
                    'state' => 'verified',
                    'evidence_ref' => 'Canonical Main Platform product lifecycle',
                ],
                [
                    'criterion' => 'Purchase boundary',
                    'value' => 'Ordering disabled while the product remains in preview.',
                    'state' => 'verified',
                    'evidence_ref' => 'Main Platform purchase lifecycle gate',
                ],
                [
                    'criterion' => 'Physical capability',
                    'value' => 'Not certified for physical calibration output.',
                    'state' => 'verified',
                    'evidence_ref' => 'Calibration repository maturity evidence',
                ],
                [
                    'criterion' => 'Demo boundary',
                    'value' => 'Synthetic browser workflow only; no hardware result is presented as measured.',
                    'state' => 'verified',
                    'evidence_ref' => 'Public Product Hub simulation contract',
                ],
            ],
            'trust' => [
                'purchase_boundary' => 'disabled',
                'demo_boundary' => 'simulation-only',
                'license_authority' => 'preview-not-commercial',
                'production_signing' => 'owner-gated-out-of-scope',
            ],
            'demo' => [
                'kind' => 'calibration',
                'simulation' => true,
                'label' => 'Interactive workflow simulation',
                'steps' => [
                    ['key' => 'setup', 'label' => 'Setup', 'detail' => 'Choose projector and camera roles.'],
                    ['key' => 'capture', 'label' => 'Capture', 'detail' => 'Preview structured-light capture sequencing.'],
                    ['key' => 'analyze', 'label' => 'Analyze', 'detail' => 'See how correspondence and geometry checks fit together.'],
                    ['key' => 'results', 'label' => 'Results', 'detail' => 'Review a synthetic result state with clear non-certified labeling.'],
                ],
            ],
            'cta' => [
                'primary' => 'Launch virtual demo',
                'secondary' => 'Development preview',
            ],
        ];
    }
}
