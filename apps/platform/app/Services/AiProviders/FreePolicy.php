<?php

declare(strict_types=1);

namespace App\Services\AiProviders;

use RuntimeException;

/**
 * Global zero-spend admission rule. Cloud inference is admitted only where the provider documents
 * a free rule AND the owner has verified it (allowlist) or the id carries the documented free
 * marker. Unknown pricing or credits mean deny. There is deliberately no "allow paid" switch:
 * enabling billed inference needs a separately approved and audited billing policy, not a flag.
 */
final class FreePolicy
{
    /** @param list<string> $freeModels owner-verified free model ids for the allowlist tier */
    public static function inferenceAllowed(string $freeTier, string $model, array $freeModels = []): bool
    {
        return match ($freeTier) {
            'allowlist' => in_array($model, $freeModels, true),
            'model-suffix' => str_ends_with($model, ':free'),
            default => false,
        };
    }

    /** @param list<string> $freeModels */
    public static function assertInferenceAllowed(string $freeTier, string $model, array $freeModels = []): void
    {
        if (! self::inferenceAllowed($freeTier, $model, $freeModels)) {
            throw new RuntimeException('zero_spend_blocked');
        }
    }
}
