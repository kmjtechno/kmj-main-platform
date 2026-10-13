<?php

declare(strict_types=1);

namespace App\Services\AiProviders;

use RuntimeException;

/**
 * Zero-spend guard. A provider that is "free only" may run inference only where the
 * provider documents as free AND the owner has verified (allowlist) or the id carries the documented
 * free marker. A free account does not make every model free. Turning free-only off is an explicit,
 * recorded opt-in to paid use; nothing here ever verifies or invents a balance.
 */
final class FreePolicy
{
    /** @param list<string> $freeModels owner-verified free model ids for the allowlist tier */
    public static function inferenceAllowed(string $freeTier, bool $freeOnly, string $model, array $freeModels = []): bool
    {
        if (! $freeOnly) {
            return true;
        }

        return match ($freeTier) {
            'allowlist' => in_array($model, $freeModels, true),
            'model-suffix' => str_ends_with($model, ':free'),
            default => false,
        };
    }

    /** @param list<string> $freeModels */
    public static function assertInferenceAllowed(string $freeTier, bool $freeOnly, string $model, array $freeModels = []): void
    {
        if (! self::inferenceAllowed($freeTier, $freeOnly, $model, $freeModels)) {
            throw new RuntimeException('zero_spend_blocked');
        }
    }
}
