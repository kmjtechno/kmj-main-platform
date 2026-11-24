<?php

declare(strict_types=1);

namespace App\Services\Commerce;

use JsonException;

/**
 * Read-only, owner-console price research. Never authoritative for checkout,
 * subscription settlement, entitlements or license signing.
 */
final class CommercialPriceProposalBook
{
    /**
     * @return array{version: string, status: string, products: list<array<string, mixed>>}
     */
    public function snapshot(): array
    {
        $unavailable = [
            'version' => 'unavailable',
            'status' => 'unavailable',
            'products' => [],
        ];
        $file = resource_path('private/kmj-commercial-pricebook-20261123.json');

        if (! is_file($file) || filesize($file) > 65536) {
            return $unavailable;
        }

        $contents = file_get_contents($file);
        if ($contents === false) {
            return $unavailable;
        }

        try {
            $book = json_decode($contents, true, 512, JSON_THROW_ON_ERROR);
        } catch (JsonException) {
            return $unavailable;
        }

        // A draft is deliberately not a payable price; abort if any flag
        // suggests publication, money movement or license authority.
        if (! is_array($book)
            || ($book['status'] ?? null) !== 'owner_review_only'
            || ($book['checkout_enabled'] ?? null) !== false
            || ($book['live_payment_enabled'] ?? null) !== false
            || ($book['approved_for_commercial_orders'] ?? null) !== false
            || ($book['automatic_license_issuance_enabled'] ?? null) !== false
            || ($book['customer_visible'] ?? null) !== false
            || ! is_array($book['products'] ?? null)) {
            return $unavailable;
        }

        $products = [];
        foreach ($book['products'] as $product) {
            if (! is_array($product)
                || ($product['pricing_status'] ?? null) !== 'review_only'
                || ($product['ready_to_sell'] ?? null) !== false
                || ! is_string($product['slug'] ?? null)
                || ! preg_match('/\\Akmj-[a-z0-9-]+\\z/D', $product['slug'])
                || ! is_string($product['name'] ?? null)
                || ! is_string($product['entry_plan'] ?? null)
                || ! is_string($product['unit'] ?? null)) {
                return $unavailable;
            }

            foreach (['entry_amount_minor', 'annual_amount_minor'] as $key) {
                $amount = $product[$key] ?? null;
                if ($amount !== null && (! is_int($amount) || $amount < 0)) {
                    return $unavailable;
                }
            }

            $products[] = [
                'slug' => $product['slug'],
                'name' => $product['name'],
                'entry_plan' => $product['entry_plan'],
                'entry_amount_minor' => $product['entry_amount_minor'] ?? null,
                'annual_amount_minor' => $product['annual_amount_minor'] ?? null,
                'unit' => $product['unit'],
                'quote_only' => ($product['quote_only'] ?? false) === true,
                'existing_owner_reference' => ($product['pricing_source'] ?? '') === 'owner_approved_existing_reference',
            ];
        }

        if (count($products) !== 14) {
            return $unavailable;
        }

        return [
            'version' => (string) ($book['version'] ?? 'unknown'),
            'status' => 'owner_review_only',
            'products' => $products,
        ];
    }
}
