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
            ->whereIn('slug', $this->publicSlugs())
            ->get()
            ->keyBy('slug');

        return collect($this->publicSlugs())
            ->map(fn (string $slug): ?array => $this->present($products->get($slug)))
            ->filter()
            ->values()
            ->all();
    }

    /**
     * @return array<int, string>
     */
    public function slugs(): array
    {
        return $this->publicSlugs();
    }

    /**
     * @return array<string, mixed>|null
     */
    public function find(string $slug): ?array
    {
        if (! in_array($slug, $this->publicSlugs(), true)) {
            return null;
        }

        return $this->present(Product::query()->where('slug', $slug)->first());
    }

    /**
     * @return array<int, string>
     */
    private function publicSlugs(): array
    {
        return [
            CloudOSProductCatalog::SLUG,
            KmjProductCatalog::CALIBRATION_SLUG,
            KmjProductCatalog::DESKTOP_COMMANDER_SLUG,
            KmjProductCatalog::FORGE_SLUG,
            KmjProductCatalog::CONNECT_SLUG,
            KmjProductCatalog::CLOUD_NEXUS_SLUG,
            KmjProductCatalog::AGENT_SLUG,
            KmjProductCatalog::CREATIVE_STUDIO_SLUG,
            KmjProductCatalog::CINEMA_PLATFORM_SLUG,
            KmjProductCatalog::DOME_360_SLUG,
            KmjProductCatalog::CINEMA_PLAYER_SLUG,
            KmjProductCatalog::LICENSING_HUB_SLUG,
        ];
    }

    /**
     * @return array<string, mixed>|null
     */
    private function present(?Product $product): ?array
    {
        if ($product === null) {
            return null;
        }

        $slug = (string) $product->getAttribute('slug');

        $presented = match ($slug) {
            CloudOSProductCatalog::SLUG => $this->cloudOS($product),
            KmjProductCatalog::CALIBRATION_SLUG => $this->calibration(),
            KmjProductCatalog::DESKTOP_COMMANDER_SLUG => $this->desktopCommander(),
            KmjProductCatalog::FORGE_SLUG => $this->forge(),
            KmjProductCatalog::CONNECT_SLUG => $this->connect(),
            KmjProductCatalog::CLOUD_NEXUS_SLUG => $this->cloudNexus(),
            KmjProductCatalog::AGENT_SLUG => $this->agent(),
            KmjProductCatalog::CREATIVE_STUDIO_SLUG => $this->creativeStudio(),
            KmjProductCatalog::CINEMA_PLATFORM_SLUG => $this->cinemaPlatform(),
            KmjProductCatalog::DOME_360_SLUG => $this->immersiveCinemaProduct(
                KmjProductCatalog::DOME_360_SLUG,
                KmjProductCatalog::DOME_360_NAME,
                '360° immersive dome systems',
                'A roadmap product family for panoramic dome playback, projection and synchronized immersive experiences.',
            ),
            KmjProductCatalog::CINEMA_PLAYER_SLUG => $this->immersiveCinemaProduct(
                KmjProductCatalog::CINEMA_PLAYER_SLUG,
                KmjProductCatalog::CINEMA_PLAYER_NAME,
                'Professional cinema playback software',
                'A roadmap playback product for reliable professional cinema and immersive-system media delivery.',
            ),
            KmjProductCatalog::LICENSING_HUB_SLUG => $this->licensingHub(),
            default => null,
        };

        if ($presented === null) {
            return null;
        }

        return [
            ...$presented,
            'category' => $this->categoryForSlug($slug),
            'family' => str_starts_with($slug, 'kmj-') && (
                str_contains($slug, 'cinema')
                || $slug === KmjProductCatalog::DOME_360_SLUG
            )
                ? 'KMJ Cinema & Immersive Systems'
                : null,
        ];
    }

    private function categoryForSlug(string $slug): string
    {
        return match ($slug) {
            CloudOSProductCatalog::SLUG,
            KmjProductCatalog::CLOUD_NEXUS_SLUG => 'Platform & Infrastructure',
            KmjProductCatalog::FORGE_SLUG,
            KmjProductCatalog::AGENT_SLUG => 'Engineering & Automation',
            KmjProductCatalog::CALIBRATION_SLUG => 'Calibration & Vision Systems',
            KmjProductCatalog::CONNECT_SLUG => 'Secure Access & Connectivity',
            KmjProductCatalog::LICENSING_HUB_SLUG => 'Commerce & Licensing',
            KmjProductCatalog::CREATIVE_STUDIO_SLUG,
            KmjProductCatalog::CINEMA_PLATFORM_SLUG,
            KmjProductCatalog::DOME_360_SLUG,
            KmjProductCatalog::CINEMA_PLAYER_SLUG => 'Media & Immersive Experience',
            default => 'KMJ TECHNO Products',
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
    private function desktopCommander(): array
    {
        return $this->developmentProduct(
            slug: KmjProductCatalog::DESKTOP_COMMANDER_SLUG,
            name: KmjProductCatalog::DESKTOP_COMMANDER_NAME,
            lifecycle: 'public-beta',
            lifecycleLabel: 'Free public beta',
            eyebrow: 'Local-first engineering command center',
            headline: 'Operate projects and servers from one secure desktop control plane.',
            summary: 'KMJ Desktop Commander runs engineering operations on the customer device and customer-controlled servers. The KMJ Main Platform is reserved for lightweight account, entitlement, release and billing control rather than carrying project workloads.',
            status: 'The v0.1 line is being verified for Windows distribution. Public-beta access is free while release, entitlement and safety gates mature; paid plans are not enabled until those gates pass.',
            proof: [
                [
                    'title' => 'Local-first execution',
                    'detail' => 'Project inspection, Git checks and quality gates execute through the customer-controlled OpenSSH path instead of consuming KMJ server compute.',
                    'state' => 'repository-verified',
                ],
                [
                    'title' => 'Deny-by-default policy',
                    'detail' => 'Remote operations use fixed policy-gated presets and do not expose arbitrary shell execution through the desktop UI.',
                    'state' => 'repository-verified',
                ],
                [
                    'title' => 'Free before monetization',
                    'detail' => 'Commercial purchase remains disabled during public beta. Paid conversion will be enabled only after signed releases, entitlement enforcement and billing are verified end to end.',
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
            slug: KmjProductCatalog::FORGE_SLUG,
            name: KmjProductCatalog::FORGE_NAME,
            lifecycle: 'early-development',
            lifecycleLabel: 'Early development',
            eyebrow: 'AI software engineering framework',
            headline: 'A universal, local-capable and provider-agnostic engineering framework.',
            summary: 'KMJ Forge is an open-source engineering framework intended to understand, plan, build, test, debug, review and ship software across languages and platforms.',
            status: 'Repository evidence identifies KMJ Forge as early development / v0.1.x bootstrap. It is not presented as a finished commercial product.',
            proof: [
                [
                    'title' => 'Open-source product foundation',
                    'detail' => 'The KMJ Forge repository defines an executable Python package, CLI bootstrap, tests, adapters and versioned roadmap.',
                    'state' => 'repository-verified',
                ],
                [
                    'title' => 'Provider-agnostic direction',
                    'detail' => 'The roadmap is explicitly model-, provider-, IDE-, language- and platform-agnostic.',
                    'state' => 'roadmap-verified',
                ],
                [
                    'title' => 'Commercial access disabled',
                    'detail' => 'No Main Platform commercial entitlement is enabled while Forge remains in early development.',
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
            slug: KmjProductCatalog::CONNECT_SLUG,
            name: KmjProductCatalog::CONNECT_NAME,
            lifecycle: 'planned',
            lifecycleLabel: 'Planned',
            eyebrow: 'Secure remote desktop',
            headline: 'A roadmap product for secure remote access using the shared KMJ account and licensing platform.',
            summary: 'KMJ Connect is the roadmap name for KMJ TECHNO’s remote-desktop product line. The commercial platform is designed for it, but a verified customer release is not yet available.',
            status: 'Roadmap-defined product. A production-ready KMJ Connect release has not been verified, so download, pricing and purchase remain disabled.',
            proof: [
                [
                    'title' => 'Roadmap-defined product',
                    'detail' => 'The KMJ Unified Platform roadmap defines KMJ Connect as the secure remote desktop product and a consumer of the shared entitlement and licensing system.',
                    'state' => 'roadmap-verified',
                ],
                [
                    'title' => 'Launch gate preserved',
                    'detail' => 'Remote-desktop commercial launch remains behind licensing and measured performance gates.',
                    'state' => 'roadmap-verified',
                ],
                [
                    'title' => 'No fake screenshots or benchmarks',
                    'detail' => 'Public presentation does not claim an available app, benchmark or download until real product evidence exists.',
                    'state' => 'fail-closed',
                ],
            ],
        );
    }

    /**
     * @return array<string, mixed>
     */
    private function cloudNexus(): array
    {
        return $this->developmentProduct(
            slug: KmjProductCatalog::CLOUD_NEXUS_SLUG,
            name: KmjProductCatalog::CLOUD_NEXUS_NAME,
            lifecycle: 'development',
            lifecycleLabel: 'Development',
            eyebrow: 'Autonomous engineering IDE',
            headline: 'A separate Code-OSS-based engineering environment for developing and operating KMJ systems.',
            summary: 'KMJ Cloud Nexus is architecturally separate from the Main Platform. It is intended to operate through released APIs and governed contracts rather than sharing the website database.',
            status: 'The master platform blueprint defines Cloud Nexus as a separate autonomous engineering IDE. A customer-ready public release is not yet verified.',
            proof: [
                [
                    'title' => 'Hard system boundary',
                    'detail' => 'Cloud Nexus remains separate from the Main Platform and must not become the website backend or share unrestricted database access.',
                    'state' => 'roadmap-verified',
                ],
                [
                    'title' => 'Code-OSS foundation',
                    'detail' => 'The current engineering repository is based on the Code-OSS workbench and remains under active product development.',
                    'state' => 'repository-observed',
                ],
                [
                    'title' => 'Public release not asserted',
                    'detail' => 'No production download or commercial access is published until product-specific release evidence is verified.',
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
            slug: KmjProductCatalog::AGENT_SLUG,
            name: KmjProductCatalog::AGENT_NAME,
            lifecycle: 'development',
            lifecycleLabel: 'Development',
            eyebrow: 'Autonomous software engineering agent',
            headline: 'An autonomous engineering agent for inspecting, changing, testing and verifying real software projects.',
            summary: 'KMJ Agent is a separate autonomous software-engineering product under active P1 development. Its repository contains a working desktop/daemon direction, durable task state and verified-free provider routing work.',
            status: 'Repository state identifies KMJ Agent as IN_PROGRESS in P1. A customer-ready public release and commercial entitlement are not yet verified.',
            proof: [
                [
                    'title' => 'Independent product identity',
                    'detail' => 'The repository contract defines KMJ Agent as an autonomous software-engineering AI agent rather than an IDE or CLI wrapper.',
                    'state' => 'repository-verified',
                ],
                [
                    'title' => 'Active implementation',
                    'detail' => 'Current repository state tracks native desktop, daemon, approvals, diff review and verified-free execution work.',
                    'state' => 'repository-observed',
                ],
                [
                    'title' => 'Commercial access disabled',
                    'detail' => 'No public download or paid entitlement is asserted until release evidence is verified.',
                    'state' => 'fail-closed',
                ],
            ],
        );
    }

    /**
     * @return array<string, mixed>
     */
    private function creativeStudio(): array
    {
        return $this->developmentProduct(
            slug: KmjProductCatalog::CREATIVE_STUDIO_SLUG,
            name: KmjProductCatalog::CREATIVE_STUDIO_NAME,
            lifecycle: 'roadmap',
            lifecycleLabel: 'Roadmap',
            eyebrow: 'Autonomous creative production studio',
            headline: 'A roadmap product for turning an idea into a finished creative production through an automated media workflow.',
            summary: 'KMJ Creative Studio is defined in the product roadmap as a separate autonomous production system for scripted image, video, voice, sound, editing, quality review and export workflows.',
            status: 'Architecture and product roadmap exist, but a verified customer-ready repository/release is not currently published in the connected KMJ GitHub portfolio.',
            proof: [
                [
                    'title' => 'Roadmap-defined product',
                    'detail' => 'The KMJ Creative Studio master roadmap defines a separate product under the KMJ TECHNO platform.',
                    'state' => 'roadmap-verified',
                ],
                [
                    'title' => 'Shared-platform boundary',
                    'detail' => 'The roadmap keeps Creative Studio separate while reusing shared KMJ account and platform services.',
                    'state' => 'roadmap-verified',
                ],
                [
                    'title' => 'No synthetic release claim',
                    'detail' => 'Downloads, benchmarks and production readiness remain unpublished until implementation evidence exists.',
                    'state' => 'fail-closed',
                ],
            ],
        );
    }

    /**
     * @return array<string, mixed>
     */
    private function cinemaPlatform(): array
    {
        return [
            ...$this->developmentProduct(
                slug: KmjProductCatalog::CINEMA_PLATFORM_SLUG,
                name: KmjProductCatalog::CINEMA_PLATFORM_NAME,
                lifecycle: 'development',
                lifecycleLabel: 'Active development',
                eyebrow: 'Professional immersive cinema platform',
                headline: 'One governed cinema platform spanning 5D through 16D and 5DX configurations.',
                summary: 'KMJ Cinema Platform is the canonical product family for synchronized playback, motion, environmental effects and immersive cinema configurations. 5D, 7D, 9D, 12D, 14D, 16D and 5DX are deployment variants of this platform, not separate software products.',
                status: 'Active product-development stream. Variant labels describe supported roadmap configurations; commercial availability remains fail-closed until verified release and licensing gates are complete.',
                proof: [
                    [
                        'title' => 'One canonical product authority',
                        'detail' => 'All D/5DX configurations bind to the KMJ Cinema Platform product identity for access, entitlement and licensing.',
                        'state' => 'platform-verified',
                    ],
                    [
                        'title' => 'Variant-based architecture',
                        'detail' => '5D, 7D, 9D, 12D, 14D, 16D and 5DX are configuration variants within the same product family.',
                        'state' => 'roadmap-verified',
                    ],
                    [
                        'title' => 'Commercial release not asserted',
                        'detail' => 'No production download or purchase is exposed until a current release is independently accepted.',
                        'state' => 'fail-closed',
                    ],
                ],
            ),
            'variants' => KmjProductCatalog::CINEMA_VARIANTS,
            'family' => 'KMJ Cinema & Immersive Systems',
        ];
    }

    /**
     * @return array<string, mixed>
     */
    private function licensingHub(): array
    {
        return $this->developmentProduct(
            slug: KmjProductCatalog::LICENSING_HUB_SLUG,
            name: KmjProductCatalog::LICENSING_HUB_NAME,
            lifecycle: 'roadmap',
            lifecycleLabel: 'Roadmap',
            eyebrow: 'Software licensing & subscription platform',
            headline: 'A governed licensing platform for selling and controlling software access online.',
            summary: 'KMJ Licensing Hub is the roadmap commercial licensing product for customer organizations that need software entitlements, subscription access, license issuance, validation, revocation and centralized product control from the KMJ Main Platform.',
            status: 'Roadmap-defined SaaS product. Commercial self-service, billing and external customer release remain disabled until product-specific release and payment gates are verified.',
            proof: [
                [
                    'title' => 'Main Platform licensing authority',
                    'detail' => 'The platform already provides entitlement, issuance, validation and revocation foundations that this product can expose as a governed customer service.',
                    'state' => 'platform-verified',
                ],
                [
                    'title' => 'Recurring-revenue direction',
                    'detail' => 'The roadmap supports subscription and licensed software access without treating payment confirmation as authorization by itself.',
                    'state' => 'roadmap-verified',
                ],
                [
                    'title' => 'Commercial release fail-closed',
                    'detail' => 'No paid self-service or third-party licensing claim is exposed until billing, support and production release gates are verified.',
                    'state' => 'fail-closed',
                ],
            ],
        );
    }

    /**
     * @return array<string, mixed>
     */
    private function immersiveCinemaProduct(
        string $slug,
        string $name,
        string $eyebrow,
        string $summary,
    ): array {
        return $this->developmentProduct(
            slug: $slug,
            name: $name,
            lifecycle: 'roadmap',
            lifecycleLabel: 'Roadmap',
            eyebrow: $eyebrow,
            headline: 'Part of the KMJ Cinema & Immersive Systems roadmap.',
            summary: $summary,
            status: 'Roadmap-defined product. Commercial availability, hardware compatibility and customer release are not asserted until product-specific evidence and licensing gates are complete.',
            proof: [
                [
                    'title' => 'Main Platform catalog authority',
                    'detail' => 'The product has a canonical KMJ Main Platform identity so future entitlement and licensing can bind to one authoritative slug.',
                    'state' => 'platform-verified',
                ],
                [
                    'title' => 'Cinema-family boundary',
                    'detail' => 'The product belongs to the KMJ Cinema & Immersive Systems family while remaining independently licensable.',
                    'state' => 'roadmap-verified',
                ],
                [
                    'title' => 'Commercial access fail-closed',
                    'detail' => 'Purchase, download and production claims remain disabled until a verified release and active entitlement policy exist.',
                    'state' => 'fail-closed',
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
                'label' => 'No public demo yet',
                'steps' => [],
            ],
            'cta' => [
                'primary' => 'View product status',
                'secondary' => $lifecycleLabel,
            ],
        ];
    }
}
