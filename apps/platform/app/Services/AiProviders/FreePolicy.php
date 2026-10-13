<?php

declare(strict_types=1);

namespace App\Services\AiProviders;

use RuntimeException;

/**
 * Zero-spend guard. A provider that is "free only" may run inference only where the
 * provider documents a free tier for that model. Turning free-only off is an explicit,
 * recorded opt-in to paid use; nothing here ever verifies or invents a balance.
 */
final class FreePolicy
{
    public static function inferenceAllowed(string $freeTier, bool $freeOnly, string $model): bool
    {
        if (! $freeOnly) {
            return true;
        }

        return match ($freeTier) {
            'plan' => true,
            'model-suffix' => str_ends_with($model, ':free'),
            default => false,
        };
    }

    public static function assertInferenceAllowed(string $freeTier, bool $freeOnly, string $model): void
    {
        if (! self::inferenceAllowed($freeTier, $freeOnly, $model)) {
            throw new RuntimeException('zero_spend_blocked');
        }
    }
}
