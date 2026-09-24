<?php

namespace App\Services\Commerce;

use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Entitlements\Models\EntitlementPolicy;

final class PublicProductCatalog
{
    private const PUBLIC_SLUGS = [
        CloudOSProductCatalog::SLUG,
        KmjProductCatalog::CALIBRATION_SLUG,
        KmjProductCatalog::CLOUD_NEXUS_SLUG,
        KmjProductCatalog::FORGE_SLUG,
        KmjProductCatalog::AGENT_SLUG,
        KmjProductCatalog::CONNECT_SLUG,
    ];

    /**
     * @return array<int, array<string, mixed>>
     */
    public function all(): array
    {
        $products = Product::query()
            ->whereIn('slug', self::PUBLIC_SLUGS)
            ->get()
            ->keyBy('slug');

        return collect(self::PUBLIC_SLUGS)
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
        if (! in_array($slug, self::PUBLIC_SLUGS, true)) {
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
            KmjProductCatalog::CLOUD_NEXUS_SLUG => $this->cloudNexus(),
            KmjProductCatalog::FORGE_SLUG => $this->forge(),
            KmjProductCatalog::AGENT_SLUG => $this->agent(),
            KmjProductCatalog::CONNECT_SLUG => $this->connect(),
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

    /**
     * @return array<string, mixed>
     */
    private function cloudNexus(): array
    {
        return $this->developmentProduct(
            KmjProductCatalog::CLOUD_NEXUS_SLUG,
            KmjProductCatalog::CLOUD_NEXUS_NAME,
            'development',
            'Development',
            'Autonomous cloud IDE',
            'A KMJ-branded Code-OSS workbench for autonomous engineering workflows.',
            'KMJ Cloud Nexus is the roadmap identity for the separate engineering IDE. Repository product metadata currently names the application KMJ Autonomous Cloud IDE / KMJ Cloud IDE.',
            'Repository and KMJ-branded product metadata are present; no commercial release is claimed.',
            [
                [
                    'title' => 'KMJ product metadata',
                    'detail' => 'The product definition declares KMJ Autonomous Cloud IDE, KMJ Cloud IDE and KMJ-specific application identifiers.',
                    'state' => 'repository-verified',
                ],
                [
                    'title' => 'Separate system boundary',
                    'detail' => 'Cloud Nexus remains an independent engineering IDE and does not become the Main Platform website or database.',
                    'state' => 'roadmap-verified',
                ],
                [
                    'title' => 'Release truth',
                    'detail' => 'The public portfolio shows development status until a separately verified commercial release exists.',
                    'state' => 'fail-closed',
                ],
            ],
        );
    }

    /**
     * @return array<string, mixed>
     */
    private function forge(): array
    {
        return $this->developmentProduct(
            KmjProductCatalog::FORGE_SLUG,
            KmjProductCatalog::FORGE_NAME,
            'early-development',
            'Early development',
            'AI software engineering framework',
            'A free-first, local-capable and provider-agnostic engineering framework from KMJ TECHNO.',
            'KMJ Forge is a separate open-source engineering framework intended for reusable workflows, skills, tools, adapters and evidence-driven software delivery.',
            'Repository status is explicitly early development / v0.1.x bootstrap.',
            [
                [
                    'title' => 'Open-source foundation',
                    'detail' => 'The repository ships an executable Python bootstrap, tests, schemas, adapters and an Apache-2.0 project structure.',
                    'state' => 'repository-verified',
                ],
                [
                    'title' => 'Provider-agnostic direction',
                    'detail' => 'The project is explicitly model-, provider-, language-, IDE- and platform-agnostic.',
                    'state' => 'repository-verified',
                ],
                [
                    'title' => 'Lifecycle boundary',
                    'detail' => 'Early-development status is shown publicly; no production-readiness claim is made.',
                    'state' => 'fail-closed',
                ],
            ],
        );
    }

    /**
     * @return array<string, mixed>
     */
    private function agent(): array
    {
        return $this->developmentProduct(
            KmjProductCatalog::AGENT_SLUG,
            KmjProductCatalog::AGENT_NAME,
            'development',
            'Development',
            'Autonomous software engineering agent',
            'An autonomous software engineering agent project in the KMJ TECHNO portfolio.',
            'The KMJ Agent repository exists with an autonomous software engineering scope, but current public repository evidence is still minimal.',
            'Repository scaffold is present; commercial availability and production capability are not declared.',
            [
                [
                    'title' => 'Dedicated project',
                    'detail' => 'KMJ Agent is maintained as its own repository rather than being presented as a hidden Main Platform capability.',
                    'state' => 'repository-verified',
                ],
                [
                    'title' => 'Conservative public claims',
                    'detail' => 'The site publishes only the repository-declared autonomous software engineering scope.',
                    'state' => 'evidence-limited',
                ],
                [
                    'title' => 'No commercial claim',
                    'detail' => 'Purchase and production-readiness remain disabled until stronger release evidence exists.',
                    'state' => 'fail-closed',
                ],
            ],
        );
    }

    /**
     * @return array<string, mixed>
     */
    private function connect(): array
    {
        return $this->developmentProduct(
            KmjProductCatalog::CONNECT_SLUG,
            KmjProductCatalog::CONNECT_NAME,
            'planned-development',
            'Planned / development',
            'Secure remote desktop',
            'Secure Remote Desktop by KMJ Techno — a roadmap product for governed remote access.',
            'KMJ Connect is the locked working roadmap name for the remote-desktop product. Commercial launch is intentionally after the shared licensing platform is proven.',
            'Roadmap-defined product; a working commercial release is not yet verified.',
            [
                [
                    'title' => 'Roadmap product identity',
                    'detail' => 'The master product roadmap names KMJ Connect as the secure remote-desktop product and second consumer of the shared commercial platform.',
                    'state' => 'roadmap-verified',
                ],
                [
                    'title' => 'Commercial dependency',
                    'detail' => 'The roadmap explicitly places shared licensing and Calibration integration ahead of KMJ Connect commercial launch.',
                    'state' => 'roadmap-verified',
                ],
                [
                    'title' => 'Real-media rule',
                    'detail' => 'Product screenshots must come from the actual application as it matures; fake UI screenshots are not published.',
                    'state' => 'truth-locked',
                ],
            ],
        );
    }

    /**
     * @param  array<int, array<string, string>>  $proof
     * @return array<string, mixed>
     */
    private function developmentProduct(
        string $slug,
        string $name,
        string $lifecycle,
        string $lifecycleLabel,
        string $eyebrow,
        string $headline,
        string $summary,
        string $status,
        array $proof,
    ): array {
        return [
            'slug' => $slug,
            'name' => $name,
            'lifecycle' => $lifecycle,
            'lifecycle_label' => $lifecycleLabel,
            'purchase_enabled' => false,
            'eyebrow' => $eyebrow,
            'headline' => $headline,
            'summary' => $summary,
            'truth' => [
                'status' => $status,
            ],
            'proof' => $proof,
            'demo' => [
                'kind' => 'none',
                'simulation' => false,
                'label' => 'Verified product status',
                'steps' => [],
            ],
            'cta' => [
                'primary' => 'View product status',
                'secondary' => $lifecycleLabel,
            ],
        ];
    }
}