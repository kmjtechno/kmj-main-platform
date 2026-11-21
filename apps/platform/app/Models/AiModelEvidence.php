<?php

declare(strict_types=1);

namespace App\Models;

use Carbon\CarbonInterface;
use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;

/**
 * Real types for columns whose casts Larastan reads as plain strings (json, timestamps).
 *
 * @property string $id
 * @property string $organization_id
 * @property string $ai_provider_id
 * @property string $model_id
 * @property string $price_evidence_url
 * @property string $price_evidence_note
 * @property CarbonInterface $verified_at
 * @property CarbonInterface $expires_at
 * @property string $data_handling
 * @property array<int, string>|null $capabilities
 * @property int|null $context_limit
 * @property int|null $verified_by
 * @property CarbonInterface|null $revoked_at
 */
final class AiModelEvidence extends Model
{
    use HasUuids;

    protected $table = 'ai_model_evidence';

    /** @var list<string> */
    protected $guarded = [];

    /** @return array<string, string> */
    protected function casts(): array
    {
        return [
            'capabilities' => 'array',
            'verified_at' => 'datetime',
            'expires_at' => 'datetime',
            'revoked_at' => 'datetime',
            'context_limit' => 'integer',
        ];
    }

    public function isCurrent(): bool
    {
        return $this->revoked_at === null && $this->expires_at->isFuture();
    }
}
