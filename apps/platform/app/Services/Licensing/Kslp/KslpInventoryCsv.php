<?php

declare(strict_types=1);

namespace App\Services\Licensing\Kslp;

use RuntimeException;

/**
 * Read-only organization-scoped CSV inventory formatting. NEVER output secret
 * license keys, hashes, customer identities or device fingerprints.
 */
final class KslpInventoryCsv
{
    public const MAX_ROWS = 1000;

    public const COLUMNS = [
        'product_code', 'application_name', 'license_id', 'masked_key_prefix',
        'license_plan', 'license_status', 'issued_at', 'expires_at',
        'first_activated_at',
    ];

    /**
     * Protect spreadsheet consumers against formulas and control character injection.
     * This does not alter stored application names or immutable product identities.
     */
    public static function safeCell(mixed $value): string
    {
        if ($value === null) {
            return '';
        }

        $text = (string) $value;
        $text = preg_replace('/[\x00-\x1F\x7F]/', ' ', $text) ?? '';
        if (preg_match('/\A\s*[=+\-@]/', $text) === 1) {
            return "'".$text;
        }

        return $text;
    }

    /**
     * @param resource $stream
     * @param array<int, mixed> $cells
     */
    public static function writeRow($stream, array $cells): void
    {
        if (fputcsv($stream, array_map(self::safeCell(...), $cells), ',', '"', '') === false) {
            throw new RuntimeException('KSLP_INVENTORY_CSV_WRITE_FAILED');
        }
    }
}
