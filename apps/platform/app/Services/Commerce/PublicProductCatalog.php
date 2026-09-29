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
        return Product::query()
            ->whereIn('slug', $this->publicSlugs())
            ->where('is_public', true)
            ->orderBy('sort_order')
            ->orderBy('name')
            ->get()
            ->map(fn (Product $product): ?array => $this->present($product))
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

        return $this->present(
            Product::query()
                ->where('slug', $slug)
                ->where('is_public', true)
                ->first(),
        );
    }

    /**
     * @return array<int, string>
     */
    private function publicSlugs(): array
    {
        return [
            CloudOSProductCatalog::SLUG,
            KmjProductCatalog::CALIBRATION_SLUG,
            KmjProductCatalog::FORGE_SLUG,
            KmjProductCatalog::OMNIDESK_SLUG,
            KmjProductCatalog::CLOUD_NEXUS_SLUG,
            KmjProductCatalog::AGENT_SLUG,
            KmjProductCatalog::CREATIVE_STUDIO_SLUG,
            KmjProductCatalog::CINEMA_PLATFORM_SLUG,
            KmjProductCatalog::DOME_SLUG,
            KmjProductCatalog::CINEMA_PLAYER_SLUG,
            KmjProductCatalog::IMMERSIVE_CINEMA_SUITE_SLUG,
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

        $presented = match ((string) $product->getAttribute('slug')) {
            CloudOSProductCatalog::SLUG => $this->cloudOS($product),
            KmjProductCatalog::CALIBRATION_SLUG => $this->calibration(),
            KmjProductCatalog::FORGE_SLUG => $this->forge(),
            KmjProductCatalog::CONNECT_SLUG => $this->connect(),
            KmjProductCatalog::CLOUD_NEXUS_SLUG => $this->cloudNexus(),
            KmjProductCatalog::AGENT_SLUG => $this->agent(),
            KmjProductCatalog::CREATIVE_STUDIO_SLUG => $this->creativeStudio(),
            KmjProductCatalog::CINEMA_PLATFORM_SLUG => $this->cinemaPlatform(),
            KmjProductCatalog::DOME_SLUG => $this->developmentProduct(slug: KmjProductCatalog::DOME_SLUG, name: KmjProductCatalog::DOME_NAME, lifecycle: 'development', lifecycleLabel: 'Research', eyebrow: 'Immersive 360° experience', headline: 'A dedicated immersive experience product for 360° dome and curved-screen environments.', summary: 'KMJ 360 Dome is presented as a distinct immersive product line. Commercial availability remains disabled until dedicated release evidence and deployment requirements are verified.', status: 'Dedicated product identity is defined; a customer-ready commercial release is not yet independently verified.', proof: [['title' => 'Dedicated product boundary', 'detail' => 'The Main Platform exposes KMJ 360 Dome as its own product rather than re-labelling Cinema Platform.', 'state' => 'platform-verified'], ['title' => 'Release gate preserved', 'detail' => 'Purchase remains disabled until product-specific release and deployment evidence is accepted.', 'state' => 'fail-closed']]),
            KmjProductCatalog::CINEMA_PLAYER_SLUG => $this->developmentProduct(slug: KmjProductCatalog::CINEMA_PLAYER_SLUG, name: KmjProductCatalog::CINEMA_PLAYER_NAME, lifecycle: 'development', lifecycleLabel: 'Research', eyebrow: 'Professional cinema playback', headline: 'A dedicated cinema playback product within the wider KMJ cinema technology direction.', summary: 'KMJ Cinema Player is the focused playback product identity. Engineering evidence supports an active cinema-player development stream, while public commercial release remains gated.', status: 'Active development; a current customer-ready public release is not independently verified.', proof: [['title' => 'Playback product identity', 'detail' => 'Cinema Player is kept distinct from the broader Cinema Platform product boundary.', 'state' => 'platform-verified'], ['title' => 'Commercial release not asserted', 'detail' => 'Download and purchase remain disabled until an accepted release is available.', 'state' => 'fail-closed']]),
            KmjProductCatalog::IMMERSIVE_CINEMA_SUITE_SLUG => $this->developmentProduct(slug: KmjProductCatalog::IMMERSIVE_CINEMA_SUITE_SLUG, name: KmjProductCatalog::IMMERSIVE_CINEMA_SUITE_NAME, lifecycle: 'roadmap', lifecycleLabel: 'Planned', eyebrow: 'Multi-format immersive cinema', headline: 'One immersive cinema product line spanning 5D through 16D and 5DX experiences.', summary: 'KMJ Immersive Cinema Suite groups the 5D, 7D, 9D, 12D, 14D, 16D and 5DX formats under one product boundary so customers can understand the experience family without treating each format as a separate product.', status: 'Roadmap product family; commercial availability is not asserted until product-specific release evidence is accepted.', proof: [['title' => 'Single product boundary', 'detail' => '5D, 7D, 9D, 12D, 14D, 16D and 5DX are presented as formats within one KMJ Immersive Cinema Suite product.', 'state' => 'platform-verified'], ['title' => 'Availability remains gated', 'detail' => 'No format is presented as generally available until its release and deployment evidence is verified.', 'state' => 'fail-closed']], variants: ['5D', '7D', '9D', '12D', '14D', '16D', '5DX']),
            KmjProductCatalog::LICENSING_HUB_SLUG => $this->developmentProduct(slug: KmjProductCatalog::LICENSING_HUB_SLUG, name: KmjProductCatalog::LICENSING_HUB_NAME, lifecycle: 'development', lifecycleLabel: 'Research', eyebrow: 'Entitlement + licensing authority', headline: 'The governed licensing layer designed to connect KMJ products with customer entitlements and controlled access.', summary: 'KMJ Licensing Hub represents the Main Platform licensing and entitlement capability. Sandbox issuance, validation and revocation boundaries exist; production signing and key custody remain release-gated.', status: 'Sandbox licensing capability exists; production signing authority is not yet declared customer-ready.', proof: [['title' => 'Licensing boundary', 'detail' => 'Sandbox license issuance, validation and revocation are implemented behind explicit product authority.', 'state' => 'repository-verified'], ['title' => 'Production keys fail closed', 'detail' => 'Production signing and key custody remain outside the sandbox boundary until separately approved and verified.', 'state' => 'fail-closed']]),
            default => null,
        };

        return $presented === null
            ? null
            : $this->applyManagement($product, $presented);
    }

    /**
     * @param  array<string, mixed>  $presented
     * @return array<string, mixed>
     */
    private function applyManagement(Product $product, array $presented): array
    {
        $lifecycle = (string) $product->getAttribute('lifecycle');
        $lifecycleLabel = match ($lifecycle) {
            'available' => 'Available',
            'preview' => 'Preview',
            'research' => 'Research',
            'planned' => 'Planned',
            default => $presented['lifecycle_label'],
        };
        $summary = trim((string) ($product->getAttribute('summary') ?? ''));
        $imagePath = trim((string) ($product->getAttribute('image_path') ?? ''));

        $presented['lifecycle'] = $lifecycle !== '' ? $lifecycle : $presented['lifecycle'];
        $presented['lifecycle_label'] = $lifecycleLabel;
        $presented['summary'] = $summary !== '' ? $summary : $presented['summary'];
        $presented['image_path'] = $imagePath !== '' ? $imagePath : null;
        $presented['sort_order'] = (int) $product->getAttribute('sort_order');
        $presented['licensing_enabled'] = (bool) $product->getAttribute('licensing_enabled');

        return $presented;
    }

    /**
     * @return array<string, mixed>
     */
    private function cloudOS(Product $product): array
    {
        $purchaseEnabled = (string) $product->getAttribute('status') === 'active'
            && (bool) $product->getAttribute('purchase_enabled')
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
            'lifecycle_label' => $purchaseEnabled ? 'Available' : 'Planned',
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
            'lifecycle_label' => 'Preview',
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
                'secondary' => 'Preview',
            ],
        ];
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
            lifecycleLabel: 'Research',
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
    private function omniDesk(): array
    {
        return $this->developmentProduct(
            slug: KmjProductCatalog::OMNIDESK_SLUG,
            name: KmjProductCatalog::OMNIDESK_NAME,
            lifecycle: 'pre-alpha',
            lifecycleLabel: 'Pre-alpha',
            eyebrow: 'Ultra-fast secure remote access',
            headline: 'Remote access engineered around direct connectivity, low bandwidth and minimal infrastructure overhead.',
            summary: 'KMJ OmniDesk is the active next-generation remote-access product under development by KMJ TECHNO. Its architecture prioritizes encrypted direct peer-to-peer sessions, relay only when required, adaptive weak-network behavior, native performance and commercial licensing through the KMJ Main Platform.',
            status: 'Private repository foundation is active. Customer download, production performance claims and paid access remain disabled until implementation, security, weak-network and release gates are verified.',
            proof: [
                [
                    'title' => 'Direct-first architecture',
                    'detail' => 'The product contract keeps screen and audio traffic peer-to-peer when connectivity permits, with KMJ relay infrastructure reserved for fallback or policy-required paths.',
                    'state' => 'repository-verified',
                ],
                [
                    'title' => 'Measured-performance discipline',
                    'detail' => 'Latency, bandwidth, CPU/GPU overhead, connection time, reconnect behavior and relay utilization are explicit release metrics rather than unverified marketing claims.',
                    'state' => 'repository-verified',
                ],
                [
                    'title' => 'Main Platform commercial authority',
                    'detail' => 'Trials, plans, activations and future paid entitlements are designed to remain governed by the KMJ Main Platform instead of hard-coded client unlocks.',
                    'state' => 'architecture-locked',
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
            lifecycleLabel: 'Research',
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
            lifecycleLabel: 'Research',
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
            lifecycleLabel: 'Planned',
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
            slug: KmjProductCatalog::CINEMA_PLATFORM_SLUG,
            name: KmjProductCatalog::CINEMA_PLATFORM_NAME,
            lifecycle: 'development',
            lifecycleLabel: 'Research',
            eyebrow: 'Professional cinema playback + motion platform',
            headline: 'A professional cinema platform roadmap covering playback, stereoscopic dual-projector output and synchronized motion workflows.',
            summary: 'KMJ Cinema Platform is an active product-development stream with a dedicated runtime and visual-verification handoff. Public commercial availability is kept separate from engineering progress.',
            status: 'Project handoff evidence documents an active Windows cinema-player development stream. A current customer-ready public release is not independently verified here.',
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
     * @param  array<array-key, mixed>  $variants
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
        array $variants = [],
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
            'variants' => $variants,
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
