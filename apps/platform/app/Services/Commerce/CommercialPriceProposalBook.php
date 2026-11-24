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
     * @return array{version: string, status: string, products: list<array<string, mixed>>, calibration_studio?: array<string, mixed>}
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

        if (count($products) !== 15) {
            return $unavailable;
        }

        return [
            'version' => (string) ($book['version'] ?? 'unknown'),
            'status' => 'owner_review_only',
            'products' => $products,
            'calibration_studio' => $this->calibrationStudio($book['calibration_studio_proposal'] ?? null),
        ];
    }

    /**
     * Separate proposed identity. Never alter the registered catalog or turn
     * draft plans into order terms, even when the owner can read this data.
     *
     * @return array<string, mixed>
     */
    private function calibrationStudio(mixed $proposal): array
    {
        if (! is_array($proposal)
            || ($proposal['product_slug_candidate'] ?? null) !== 'kmj-calibration-studio'
            || ($proposal['catalog_reference'] ?? null) !== 'kmj-calibration-pro'
            || ($proposal['identity_status'] ?? null) !== 'unresolved_do_not_alias_or_register'
            || ($proposal['pricing_status'] ?? null) !== 'review_only'
            || ($proposal['ready_to_sell'] ?? null) !== false
            || ($proposal['customer_visible'] ?? null) !== false
            || ($proposal['checkout_enabled'] ?? null) !== false
            || ($proposal['live_payment_enabled'] ?? null) !== false
            || ($proposal['automatic_license_issuance_enabled'] ?? null) !== false
            || ($proposal['trial_requires_card'] ?? null) !== false
            || ($proposal['trial_auto_converts'] ?? null) !== false
            || ($proposal['trial_watermark'] ?? null) !== true
            || ! is_array($proposal['plans'] ?? null)
            || count($proposal['plans']) !== 6) {
            return [];
        }

        $plans = [];
        $expected = ['trial' => 2, 'event' => 2, 'starter' => 2, 'professional' => 4, 'business' => 8, 'enterprise' => null];
        foreach ($proposal['plans'] as $plan) {
            if (! is_array($plan)
                || ! is_string($plan['code'] ?? null)
                || ! array_key_exists($plan['code'], $expected)
                || ! array_key_exists('projectors', $plan)
                || $plan['projectors'] !== $expected[$plan['code']]
                || ! is_string($plan['name'] ?? null)
                || ! is_string($plan['readiness'] ?? null)) {
                return [];
            }

            $amounts = [];
            foreach (['monthly_inr_minor', 'annual_inr_minor', 'one_time_inr_minor', 'monthly_usd_minor', 'annual_usd_minor'] as $field) {
                $amount = $plan[$field] ?? null;
                if ($amount !== null && (! is_int($amount) || $amount < 0)) {
                    return [];
                }
                $amounts[$field] = $amount;
            }
            if ($plan['code'] === 'trial' && (($plan['days'] ?? null) !== 14 || $amounts['one_time_inr_minor'] !== 0)) {
                return [];
            }
            if ($plan['code'] === 'event' && ($plan['hours'] ?? null) !== 72) {
                return [];
            }
            unset($expected[$plan['code']]);
            $plans[] = [
                'code' => $plan['code'],
                'name' => $plan['name'],
                'projectors' => $plan['projectors'],
                'readiness' => $plan['readiness'],
                ...$amounts,
            ];
        }

        return [
            'status' => 'review_only',
            'identity_status' => 'unresolved_do_not_alias_or_register',
            'plans' => $plans,
        ];
    }

}
