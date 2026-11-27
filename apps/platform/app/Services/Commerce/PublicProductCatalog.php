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
            KmjProductCatalog::CONNECT_SLUG,
            KmjProductCatalog::OMNIDESK_SLUG,
            KmjProductCatalog::CODEBRIDGE_SLUG,
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
            KmjProductCatalog::OMNIDESK_SLUG => $this->omniDesk(),
            KmjProductCatalog::CODEBRIDGE_SLUG => $this->codeBridge(),
            KmjProductCatalog::CONNECT_SLUG => $this->connect(),
            KmjProductCatalog::CLOUD_NEXUS_SLUG => $this->cloudNexus(),
            KmjProductCatalog::AGENT_SLUG => $this->agent(),
            KmjProductCatalog::CREATIVE_STUDIO_SLUG => $this->creativeStudio(),
            KmjProductCatalog::CINEMA_PLATFORM_SLUG => $this->cinemaPlatform(),
            KmjProductCatalog::DOME_SLUG => $this->developmentProduct(slug: KmjProductCatalog::DOME_SLUG, name: KmjProductCatalog::DOME_NAME, lifecycle: 'development', lifecycleLabel: 'Research', eyebrow: 'Immersive 360° experience', headline: 'Immersive experiences for 360° domes and curved screens.', summary: 'KMJ 360 Dome is an immersive experience product for 360° dome and curved screen venues. It is not on sale yet.', status: 'The product is defined. A customer release is not yet verified.', proof: [['title' => 'Its own product', 'detail' => 'KMJ 360 Dome is separate from the Cinema Platform.', 'state' => 'platform-verified'], ['title' => 'Checks before sale', 'detail' => 'Purchase stays off until release and installation evidence is accepted.', 'state' => 'fail-closed']]),
            KmjProductCatalog::CINEMA_PLAYER_SLUG => $this->developmentProduct(slug: KmjProductCatalog::CINEMA_PLAYER_SLUG, name: KmjProductCatalog::CINEMA_PLAYER_NAME, lifecycle: 'development', lifecycleLabel: 'Research', eyebrow: 'Cinema playback', headline: 'A dedicated player for cinema playback.', summary: 'KMJ Cinema Player is a cinema playback product being built by KMJ TECHNO. There is no public release yet.', status: 'Under development. There is no public release yet.', proof: [['title' => 'Focused on playback', 'detail' => 'Cinema Player is separate from the wider Cinema Platform.', 'state' => 'platform-verified'], ['title' => 'Not released', 'detail' => 'Download and purchase stay off until a release is accepted.', 'state' => 'fail-closed']]),
            KmjProductCatalog::IMMERSIVE_CINEMA_SUITE_SLUG => $this->developmentProduct(slug: KmjProductCatalog::IMMERSIVE_CINEMA_SUITE_SLUG, name: KmjProductCatalog::IMMERSIVE_CINEMA_SUITE_NAME, lifecycle: 'roadmap', lifecycleLabel: 'Planned', eyebrow: 'Multi-format immersive cinema', headline: 'One product family for 5D to 16D and 5DX experiences.', summary: 'KMJ Immersive Cinema Suite is a planned product family covering 5D, 7D, 9D, 12D, 14D, 16D and 5DX formats.', status: 'Planned. It is not on sale yet.', proof: [['title' => 'One family', 'detail' => 'All the formats sit in one product, so you do not need to compare separate ones.', 'state' => 'platform-verified'], ['title' => 'Not released', 'detail' => 'No format is offered until its release is verified.', 'state' => 'fail-closed']], variants: ['5D', '7D', '9D', '12D', '14D', '16D', '5DX']),
            KmjProductCatalog::LICENSING_HUB_SLUG => $this->developmentProduct(slug: KmjProductCatalog::LICENSING_HUB_SLUG, name: KmjProductCatalog::LICENSING_HUB_NAME, lifecycle: 'development', lifecycleLabel: 'Research', eyebrow: 'Software licensing', headline: 'Manage software licences and product access.', summary: 'KMJ Licensing Hub is being built to manage software licences and customer access. Production licensing is not released.', status: 'A test version of licensing works. Production licensing is not ready for customers.', proof: [['title' => 'Test licensing', 'detail' => 'Test licences can be issued, checked and revoked.', 'state' => 'repository-verified'], ['title' => 'Production keys not enabled', 'detail' => 'Production signing stays off until it is separately approved and verified.', 'state' => 'fail-closed']]),
            default => $this->ownerManagedProduct($product),
        };

        $slug = (string) $product->getAttribute('slug');

        return [
            ...$this->applyManagement($product, $presented),
            'category' => $this->categoryForProduct($product),
            'family' => str_contains($slug, 'cinema') || $slug === KmjProductCatalog::DOME_SLUG
                ? 'KMJ Cinema & Immersive Systems'
                : null,
        ];
    }

    private function categoryForProduct(Product $product): string
    {
        $category = (string) $product->getAttribute('category');

        return match ($category) {
            'cloud' => 'Cloud & Infrastructure',
            'cinema' => 'Cinema & Immersive',
            'industrial' => 'Industrial & Calibration',
            'developer' => 'Developer & AI',
            'business' => 'Business & Platform',
            default => $this->categoryForSlug((string) $product->getAttribute('slug')),
        };
    }

    /**
     * A governed owner-created public listing is a status page, never an
     * implicit signed license, download, public proof, or checkout.
     *
     * @return array<string, mixed>
     */
    private function ownerManagedProduct(Product $product): array
    {
        $name = (string) $product->getAttribute('name');
        $slug = (string) $product->getAttribute('slug');
        $summary = trim((string) ($product->getAttribute('summary') ?? ''));

        return $this->developmentProduct(
            slug: $slug,
            name: $name,
            lifecycle: 'roadmap',
            lifecycleLabel: 'Status',
            eyebrow: 'KMJ TECHNO product catalog',
            headline: $name,
            summary: $summary !== '' ? $summary : 'Product information is being prepared by KMJ TECHNO.',
            status: 'Listed by KMJ TECHNO. A release is not yet verified.',
            proof: [
                [
                    'title' => 'Listed by KMJ TECHNO',
                    'detail' => 'KMJ TECHNO added this product to its catalogue.',
                    'state' => 'platform-verified',
                ],
                [
                    'title' => 'Listing is not access',
                    'detail' => 'Being listed does not include purchase, licences or downloads.',
                    'state' => 'fail-closed',
                ],
            ],
        );
    }

    private function categoryForSlug(string $slug): string
    {
        return match ($slug) {
            CloudOSProductCatalog::SLUG,
            KmjProductCatalog::CLOUD_NEXUS_SLUG => 'Platform & Infrastructure',
            KmjProductCatalog::FORGE_SLUG,
            KmjProductCatalog::AGENT_SLUG => 'Engineering & Automation',
            KmjProductCatalog::CALIBRATION_SLUG => 'Calibration & Vision Systems',
            KmjProductCatalog::CONNECT_SLUG,
            KmjProductCatalog::OMNIDESK_SLUG,
            KmjProductCatalog::CODEBRIDGE_SLUG => 'Secure Access & Connectivity',
            KmjProductCatalog::LICENSING_HUB_SLUG => 'Commerce & Licensing',
            KmjProductCatalog::CREATIVE_STUDIO_SLUG,
            KmjProductCatalog::CINEMA_PLATFORM_SLUG,
            KmjProductCatalog::DOME_SLUG,
            KmjProductCatalog::CINEMA_PLAYER_SLUG,
            KmjProductCatalog::IMMERSIVE_CINEMA_SUITE_SLUG => 'Media & Immersive Experience',
            default => 'KMJ TECHNO Products',
        };
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
        $content = (array) ($product->getAttribute('content') ?? []);
        $presented['name'] = (string) $product->getAttribute('name');
        if (trim((string) ($content['headline'] ?? '')) !== '') {
            $presented['headline'] = $content['headline'];
        }
        $presented['content'] = array_intersect_key($content, array_flip(['description', 'features', 'faqs', 'banner_path', 'image_alt', 'offering_type']));
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
            'headline' => 'A cloud operating platform with access you can see and control.',
            'summary' => 'KMJ CloudOS is the cloud operating platform from KMJ TECHNO. Create a KMJ account to get access, and see your plan and licence in one place.',
            'truth' => [
                'status' => $purchaseEnabled
                    ? 'CloudOS is available now.'
                    : 'CloudOS is not on sale right now.',
            ],
            'proof' => [
                [
                    'title' => 'Access you can check',
                    'detail' => 'Your CloudOS access is recorded against your KMJ account or organization and shown in My Services.',
                    'state' => 'repository-verified',
                ],
                [
                    'title' => 'No surprise charges',
                    'detail' => 'Nothing is charged automatically. Paid access starts only after KMJ confirms your payment.',
                    'state' => 'repository-verified',
                ],
                [
                    'title' => 'A safe demo',
                    'detail' => 'The demo on this page uses sample events and never touches live systems.',
                    'state' => 'simulation',
                ],
            ],
            'demo' => [
                'kind' => 'cloudos',
                'simulation' => true,
                'label' => 'Interactive workflow simulation',
                'steps' => [
                    ['key' => 'monitor', 'label' => 'Monitor', 'detail' => 'Look at a sample service health snapshot.'],
                    ['key' => 'validate', 'label' => 'Validate', 'detail' => 'Review sample readiness checks.'],
                    ['key' => 'deploy', 'label' => 'Deploy', 'detail' => 'Preview a simulated deployment.'],
                    ['key' => 'verify', 'label' => 'Verify', 'detail' => 'Check the sample result and the rollback point.'],
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
            'headline' => 'See the calibration workflow before you touch hardware.',
            'summary' => 'KMJ Calibration Pro is a guided projector and camera calibration tool being built in C++. It is not on sale yet.',
            'truth' => [
                'physical_capability_certified' => false,
                'status' => 'The C++ foundation builds. Physical calibration is not yet certified.',
            ],
            'proof' => [
                [
                    'title' => 'Native C++ foundation',
                    'detail' => 'Built with C++23 and CMake, and checked in both debug and release builds.',
                    'state' => 'repository-verified',
                ],
                [
                    'title' => 'No false success',
                    'detail' => 'Parts that are not finished report that, instead of claiming a result.',
                    'state' => 'repository-verified',
                ],
                [
                    'title' => 'Guided product experience',
                    'detail' => 'The demo explains the Setup, Capture, Analyze and Results steps. It produces no real measurement.',
                    'state' => 'simulation',
                ],
            ],
            'demo' => [
                'kind' => 'calibration',
                'simulation' => true,
                'label' => 'Interactive workflow simulation',
                'steps' => [
                    ['key' => 'setup', 'label' => 'Setup', 'detail' => 'Choose which device is the projector and which is the camera.'],
                    ['key' => 'capture', 'label' => 'Capture', 'detail' => 'See the order of the light patterns that are captured.'],
                    ['key' => 'analyze', 'label' => 'Analyze', 'detail' => 'See how the matching and geometry checks fit together.'],
                    ['key' => 'results', 'label' => 'Results', 'detail' => 'Review a sample result, clearly marked as not certified.'],
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
            headline: 'An open-source framework for AI-assisted software engineering.',
            summary: 'KMJ Forge is an open-source framework being built to plan, build, test, review and ship software across languages and platforms.',
            status: 'KMJ Forge is in early development. It is not a finished commercial product.',
            proof: [
                [
                    'title' => 'Open-source foundation',
                    'detail' => 'A Python package with a command line tool, tests, adapters and a versioned roadmap.',
                    'state' => 'repository-verified',
                ],
                [
                    'title' => 'Works with your choice of AI',
                    'detail' => 'The roadmap does not tie Forge to one model, provider, editor, language or platform.',
                    'state' => 'roadmap-verified',
                ],
                [
                    'title' => 'Not on sale',
                    'detail' => 'Paid access stays off while Forge is in early development.',
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
            headline: 'Secure remote access that uses your KMJ account.',
            summary: 'KMJ Connect is a planned secure remote desktop product from KMJ TECHNO. There is no customer release yet.',
            status: 'KMJ Connect is planned. Download and purchase are off until a release is verified.',
            proof: [
                [
                    'title' => 'On the roadmap',
                    'detail' => 'KMJ Connect is planned to use the same account and licences as other KMJ products.',
                    'state' => 'roadmap-verified',
                ],
                [
                    'title' => 'Quality checks before launch',
                    'detail' => 'It will go on sale only after licensing and measured performance checks pass.',
                    'state' => 'roadmap-verified',
                ],
                [
                    'title' => 'Only real evidence',
                    'detail' => 'No app screenshots, speed figures or downloads are shown until they exist.',
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
            eyebrow: 'Secure remote access',
            headline: 'Remote access designed for direct connections and low bandwidth.',
            summary: 'KMJ OmniDesk is a remote access product being built for encrypted direct connections, with a relay only when needed.',
            status: 'KMJ OmniDesk is under development. Download and paid access are off until security and release checks pass.',
            proof: [
                [
                    'title' => 'Direct connection first',
                    'detail' => 'Screen and audio are designed to travel directly between devices when the network allows it.',
                    'state' => 'repository-verified',
                ],
                [
                    'title' => 'Measured, not promised',
                    'detail' => 'Speed, bandwidth and reconnect behaviour will be published only after they are measured.',
                    'state' => 'repository-verified',
                ],
                [
                    'title' => 'One KMJ account',
                    'detail' => 'Trials and plans are designed to be managed from your KMJ account.',
                    'state' => 'architecture-locked',
                ],
            ],
        );
    }

    /**
     * @return array<string, mixed>
     */
    private function codeBridge(): array
    {
        return $this->developmentProduct(
            slug: KmjProductCatalog::CODEBRIDGE_SLUG,
            name: KmjProductCatalog::CODEBRIDGE_NAME,
            lifecycle: 'research',
            lifecycleLabel: 'Research',
            eyebrow: 'Secure developer bridge',
            headline: 'Connect AI coding tools to the projects you choose.',
            summary: 'KMJ CodeBridge connects AI-assisted engineering tools to the development projects you authorise. It is not on sale yet.',
            status: 'A developer preview exists. Paid access and public download are off until the remaining security checks pass.',
            proof: [
                [
                    'title' => 'Separate from our website',
                    'detail' => 'A separate gateway and agent do the work. Your development tasks do not run inside this website.',
                    'state' => 'repository-verified',
                ],
                [
                    'title' => 'Licensed devices',
                    'detail' => 'Device sign-up, credentials and renewable licences are handled by the KMJ platform.',
                    'state' => 'platform-verified',
                ],
                [
                    'title' => 'Not on sale',
                    'detail' => 'Purchase and download stay off until sign-in, packaging and security checks are complete.',
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
            lifecycleLabel: 'Research',
            eyebrow: 'Engineering IDE',
            headline: 'A development environment for building and operating KMJ systems.',
            summary: 'KMJ Cloud Nexus is an engineering IDE being built on Code-OSS to develop and operate software systems.',
            status: 'KMJ Cloud Nexus is under development. There is no public release yet.',
            proof: [
                [
                    'title' => 'A separate product',
                    'detail' => 'Cloud Nexus is kept apart from this website and does not get open access to its database.',
                    'state' => 'roadmap-verified',
                ],
                [
                    'title' => 'Built on Code-OSS',
                    'detail' => 'The editor is based on the Code-OSS workbench and is still being developed.',
                    'state' => 'repository-observed',
                ],
                [
                    'title' => 'Not released',
                    'detail' => 'No download or paid access is offered until a release is verified.',
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
            eyebrow: 'Software engineering agent',
            headline: 'An agent designed to inspect, change, test and verify real projects.',
            summary: 'KMJ Agent is a software engineering agent being built to inspect, change, test and verify real software projects.',
            status: 'KMJ Agent is under development. There is no public release yet.',
            proof: [
                [
                    'title' => 'Its own product',
                    'detail' => 'KMJ Agent is a software engineering agent, not just an editor or command line add-on.',
                    'state' => 'repository-verified',
                ],
                [
                    'title' => 'Being built now',
                    'detail' => 'Work covers a desktop app, a background service, approvals and change review.',
                    'state' => 'repository-observed',
                ],
                [
                    'title' => 'Not on sale',
                    'detail' => 'No download or paid access is offered until a release is verified.',
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
            eyebrow: 'Creative production studio',
            headline: 'From an idea to a finished creative production.',
            summary: 'KMJ Creative Studio is a planned tool for turning a script into images, video, voice and sound in one workflow.',
            status: 'KMJ Creative Studio is planned. There is no release yet.',
            proof: [
                [
                    'title' => 'On the roadmap',
                    'detail' => 'It is defined as a separate KMJ TECHNO product.',
                    'state' => 'roadmap-verified',
                ],
                [
                    'title' => 'One KMJ account',
                    'detail' => 'It is planned to use your KMJ account and the shared platform services.',
                    'state' => 'roadmap-verified',
                ],
                [
                    'title' => 'Only real evidence',
                    'detail' => 'Downloads and performance figures appear only after the product exists.',
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
                eyebrow: 'Immersive cinema platform',
                headline: 'One cinema platform for 5D to 16D and 5DX setups.',
                summary: 'KMJ Cinema Platform is being built for synchronised playback, motion and effects across 5D to 16D and 5DX cinemas.',
                status: 'Under development. The formats listed are on the roadmap. It is not on sale yet.',
                proof: [
                    [
                        'title' => 'One product, one licence system',
                        'detail' => 'Every format uses the same product account and licensing.',
                        'state' => 'platform-verified',
                    ],
                    [
                        'title' => 'Formats, not separate products',
                        'detail' => '5D, 7D, 9D, 12D, 14D, 16D and 5DX are setups of the same platform.',
                        'state' => 'roadmap-verified',
                    ],
                    [
                        'title' => 'Not released',
                        'detail' => 'No download or purchase is offered until a release is accepted.',
                        'state' => 'fail-closed',
                    ],
                ],
            ),
            'variants' => KmjProductCatalog::CINEMA_VARIANTS,
            'family' => 'KMJ Cinema & Immersive Systems',
        ];
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
