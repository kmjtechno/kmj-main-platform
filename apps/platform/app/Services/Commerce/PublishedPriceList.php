<?php

declare(strict_types=1);

namespace App\Services\Commerce;

/**
 * Owner-approved list prices for display. This is NOT checkout, tax
 * calculation, subscription or license authority: order amounts are still
 * confirmed server-side by an operator.
 */
final class PublishedPriceList
{
    /** @return array{plans: list<array<string, mixed>>}|null */
    public function forProduct(string $slug): ?array
    {
        $file = resource_path('pricing/published-prices.json');
        $book = is_file($file)
            ? json_decode((string) file_get_contents($file), true)
            : null;

        // Fail closed: an unreadable or unexpected list publishes no price.
        if (! is_array($book)
            || ($book['currency'] ?? null) !== 'INR'
            || ($book['tax'] ?? null) !== 'plus_gst'
            || ($book['checkout_enabled'] ?? null) !== false) {
            return null;
        }

        $plans = $book['products'][$slug] ?? null;

        return is_array($plans) && $plans !== []
            ? ['plans' => array_values($plans)]
            : null;
    }
}
