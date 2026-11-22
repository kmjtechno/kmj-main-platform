<?php

declare(strict_types=1);

namespace App\Models;

use Carbon\CarbonInterface;
use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

/**
 * An owner attestation that every model of one provider matching a narrow pattern is free today
 * (ADR-004). It expires within 30 days and creates ordinary, expiring, revocable evidence rows.
 *
 * @property string $id
 * @property string $organization_id
 * @property string $ai_provider_id
 * @property string $model_pattern
 * @property string $price_evidence_url
 * @property string $price_evidence_note
 * @property string $data_handling
 * @property array<int, string>|null $capabilities
 * @property int $attested_by
 * @property CarbonInterface $attested_at
 * @property CarbonInterface $expires_at
 * @property CarbonInterface|null $revoked_at
 */
final class AiModelRule extends Model
{
    use HasUuids;

    protected $table = 'ai_model_rules';

    /** @var list<string> */
    protected $guarded = [];

    /** @return array<string, string> */
    protected function casts(): array
    {
        return [
            'capabilities' => 'array',
            'attested_at' => 'datetime',
            'expires_at' => 'datetime',
            'revoked_at' => 'datetime',
        ];
    }

    /** @return BelongsTo<AiProvider, $this> */
    public function provider(): BelongsTo
    {
        return $this->belongsTo(AiProvider::class, 'ai_provider_id');
    }

    public function isActive(): bool
    {
        return $this->revoked_at === null && $this->expires_at->isFuture();
    }
}
