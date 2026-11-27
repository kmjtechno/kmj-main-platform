<?php

namespace App\Services\Seo;

/**
 * Initial, credential-free metadata for publicly rendered Inertia pages.
 *
 * No new SSR process or database query: a product uses only the already
 * authoritative public Inertia page prop. Unknown/private pages fail closed.
 */
final class PublicInitialMetadata
{
    /**
     * @param  array<string, mixed>  $page
     * @return array<string, mixed>|null
     */
    public function forPage(array $page, string $origin): ?array
    {
        $component = $page['component'] ?? null;
        if (! is_string($component)) {
            return null;
        }

        $known = [
            'welcome' => ['/', 'KMJ TECHNO — Software, Mobile Apps, Cloud & AI Engineering', 'KMJ TECHNO builds software platforms, cloud systems, AI and immersive experiences.'],
            'products/index' => ['/products', 'Products — KMJ TECHNO', 'Explore the KMJ TECHNO product portfolio with evidence-backed lifecycle, availability and product status.'],
            'company' => ['/company', 'Company — KMJ TECHNO', 'Learn how KMJ TECHNO approaches software, cloud systems, intelligent automation, immersive technology and governed digital products.'],
            'capabilities' => ['/capabilities', 'Capabilities — KMJ TECHNO', 'Explore KMJ TECHNO focus areas across cloud platforms, AI automation, immersive calibration, security, licensing and connected digital products.'],
            'trust' => ['/trust', 'Trust Center — KMJ TECHNO', 'KMJ TECHNO Trust Center: evidence-backed product lifecycle, governed access, licensing boundaries and release integrity.'],
            'legal/index' => ['/legal', 'Legal Center — KMJ TECHNO', 'KMJ TECHNO legal terms, privacy, refunds, acceptable use and cookie policies for international software and cloud services.'],
            'legal/terms' => ['/terms', 'Terms & Conditions — KMJ TECHNO', 'Terms governing access to KMJ TECHNO websites, accounts, software, cloud services, previews, licenses and digital products.'],
            'legal/privacy' => ['/privacy', 'Privacy Policy — KMJ TECHNO', 'How KMJ TECHNO collects, uses, protects, shares and retains personal data across its international software and cloud services.'],
            'legal/refund-policy' => ['/refund-policy', 'Refund & Cancellation Policy — KMJ TECHNO', 'KMJ TECHNO refund, cancellation and digital-product remedy policy for software, subscriptions, licenses and services.'],
            'legal/acceptable-use' => ['/acceptable-use', 'Acceptable Use Policy — KMJ TECHNO', 'Rules for lawful, secure and responsible use of KMJ TECHNO software, cloud systems, automation and digital services.'],
            'legal/cookie-policy' => ['/cookie-policy', 'Cookie Policy — KMJ TECHNO', 'How KMJ TECHNO uses cookies, local storage and similar technologies for security, authentication, preferences and analytics.'],
            'products/codebridge/terms' => ['/products/kmj-codebridge/terms', 'KMJ CodeBridge Terms of Service — KMJ TECHNO', 'Product-specific terms governing use of the KMJ CodeBridge ChatGPT plugin, MCP service, gateway, agent and authorized project operations.'],
            'products/codebridge/privacy' => ['/products/kmj-codebridge/privacy', 'KMJ CodeBridge Privacy Policy — KMJ TECHNO', 'How KMJ CodeBridge handles account, device, project, tool-input, diagnostic and security data when connecting ChatGPT to authorized development environments.'],
            'products/codebridge/support' => ['/products/kmj-codebridge/support', 'KMJ CodeBridge Support — KMJ TECHNO', 'Official support, security reporting and troubleshooting guidance for the KMJ CodeBridge ChatGPT plugin and MCP service.'],
        ];

        $image = '/assets/brand/kmj-social-card.webp';
        if ($component === 'products/show') {
            $product = $page['props']['product'] ?? null;
            if (! is_array($product)) {
                return null;
            }

            $slug = $product['slug'] ?? null;
            $name = $product['name'] ?? null;
            $summary = $product['summary'] ?? null;
            if (! is_string($slug) || preg_match('/^[a-z0-9]+(?:-[a-z0-9]+)*$/D', $slug) !== 1
                || ! is_string($name) || trim($name) === ''
                || ! is_string($summary) || trim($summary) === '') {
                return null;
            }

            $path = '/products/'.$slug;
            $title = $name.' — KMJ TECHNO';
            $description = $summary;
            $image = [
                'kmj-cloudos' => '/assets/products/kmj-cloudos.webp',
                'kmj-calibration-pro' => '/assets/products/kmj-calibration.webp',
                'kmj-forge' => '/assets/products/kmj-forge.webp',
                'kmj-connect' => '/assets/products/kmj-connect.webp',
                'kmj-cloud-nexus' => '/assets/products/kmj-cloud-nexus.webp',
                'kmj-agent' => '/assets/products/kmj-agent.webp',
                'kmj-creative-studio' => '/assets/products/kmj-creative-studio.webp',
                'kmj-cinema-platform' => '/assets/products/kmj-cinema-platform.webp',
                'kmj-360-dome' => '/assets/products/kmj-360-dome.webp',
                'kmj-cinema-player' => '/assets/products/kmj-cinema-player.webp',
                'kmj-licensing-hub' => '/assets/products/kmj-licensing-hub.webp',
            ][$slug] ?? $image;
            $customImage = $product['image_path'] ?? null;
            if (is_string($customImage) && preg_match('#^/(?:assets|product-artwork)/[a-zA-Z0-9_./-]+$#D', $customImage) === 1 && ! str_contains($customImage, '..')) {
                $image = $customImage;
            }
        } elseif (array_key_exists($component, $known)) {
            [$path, $title, $description] = $known[$component];
        } else {
            return null;
        }

        $base = rtrim($origin, '/');
        $canonical = $base.$path;

        // This describes only visible, verified public facts. No fake ratings,
        // reviews, offers or release availability are ever published here.
        if ($component === 'welcome') {
            $schema = [
                ['@context' => 'https://schema.org', '@type' => 'Organization', 'name' => 'KMJ TECHNO', 'url' => $canonical],
                ['@context' => 'https://schema.org', '@type' => 'WebSite', 'name' => 'KMJ TECHNO', 'url' => $canonical],
            ];
        } elseif ($component === 'products/show') {
            $schema = [
                '@context' => 'https://schema.org',
                '@type' => ($product['content']['offering_type'] ?? 'product') === 'service' ? 'Service' : 'SoftwareApplication',
                'name' => $name,
                'description' => $description,
                'url' => $canonical,
                'brand' => ['@type' => 'Brand', 'name' => 'KMJ TECHNO'],
                'additionalProperty' => [
                    '@type' => 'PropertyValue',
                    'name' => 'Lifecycle',
                    'value' => (string) ($product['lifecycle_label'] ?? ''),
                ],
            ];
        } else {
            $schema = [
                '@context' => 'https://schema.org',
                '@type' => $component === 'company' ? 'AboutPage' : 'WebPage',
                'name' => $title,
                'url' => $canonical,
            ];
        }

        if ($component === 'products/show') {
            if (($product['content']['offering_type'] ?? 'product') === 'service') {
                unset($schema['brand'], $schema['additionalProperty']);
                $schema['provider'] = ['@type' => 'Organization', 'name' => 'KMJ TECHNO'];
            }
            $questions = [];
            // The route's visible answers win; they already include owner FAQs.
            $faqs = $page['props']['answers'] ?? $product['content']['faqs'] ?? [];
            if (is_array($faqs)) {
                foreach (array_slice($faqs, 0, 12) as $faq) {
                    if (is_array($faq) && is_string($faq['question'] ?? null) && is_string($faq['answer'] ?? null)
                        && trim($faq['question']) !== '' && trim($faq['answer']) !== '') {
                        $questions[] = ['@type' => 'Question', 'name' => $faq['question'], 'acceptedAnswer' => ['@type' => 'Answer', 'text' => $faq['answer']]];
                    }
                }
            }
            $nodes = [$schema];
            if ($questions !== []) {
                $nodes[] = ['@context' => 'https://schema.org', '@type' => 'FAQPage', 'url' => $canonical, 'mainEntity' => $questions];
            }
            $crumbs = [['Home', $base.'/'], ['Products', $base.'/products'], [$name, $canonical]];
            $nodes[] = [
                '@context' => 'https://schema.org',
                '@type' => 'BreadcrumbList',
                'itemListElement' => array_map(
                    fn (int $index, array $crumb): array => ['@type' => 'ListItem', 'position' => $index + 1, 'name' => $crumb[0], 'item' => $crumb[1]],
                    array_keys($crumbs),
                    $crumbs,
                ),
            ];
            $schema = $nodes;
        }

        $json = json_encode(
            $schema,
            JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT
                | JSON_INVALID_UTF8_SUBSTITUTE | JSON_UNESCAPED_SLASHES
        );
        if (! is_string($json)) {
            return null;
        }

        return [
            'fallback' => $this->fallback($component, $page['props'] ?? []),
            'json_ld' => $json,
            'title' => $title,
            'description' => $description,
            'canonical' => $base.$path,
            'image' => $base.$image,
            'type' => str_starts_with($component, 'legal/') || str_starts_with($component, 'products/codebridge/')
                ? 'article' : 'website',
        ];
    }

    /**
     * Readable copy of facts already visible on the page, for crawlers that do
     * not run JavaScript.
     *
     * @return array{heading: string, summary: string, answers: array<mixed>, links: list<array{href: string, label: string, text: string}>}|null
     */
    private function fallback(string $component, mixed $props): ?array
    {
        if (! is_array($props)) {
            return null;
        }

        if ($component === 'products/show') {
            return [
                'heading' => (string) $props['product']['name'],
                'summary' => (string) $props['product']['summary'],
                'answers' => array_values(is_array($props['answers'] ?? null) ? $props['answers'] : []),
                'links' => [['href' => '/products', 'label' => 'All products', 'text' => '']],
            ];
        }

        if ($component !== 'products/index' || ! is_array($props['products'] ?? null)) {
            return null;
        }

        $links = [];
        foreach ($props['products'] as $product) {
            if (is_array($product) && is_string($product['slug'] ?? null) && is_string($product['name'] ?? null)) {
                $links[] = [
                    'href' => '/products/'.rawurlencode($product['slug']),
                    'label' => $product['name'],
                    'text' => trim(($product['lifecycle_label'] ?? '').'. '.($product['summary'] ?? '')),
                ];
            }
        }

        return ['heading' => 'KMJ TECHNO products', 'summary' => '', 'answers' => [], 'links' => $links];
    }
}
