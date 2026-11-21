<?php

declare(strict_types=1);

namespace App\Models;

use Carbon\CarbonInterface;
use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;

/**
 * Bearer token for the ModelFabric OpenAI-compatible endpoint. Only the SHA-256 hash is stored.
 *
 * @property string $id
 * @property string $organization_id
 * @property string $name
 * @property string $token_hash
 * @property string $token_prefix
 * @property bool $private_source
 * @property CarbonInterface $expires_at
 * @property CarbonInterface|null $last_used_at
 * @property CarbonInterface|null $revoked_at
 */
final class AiModelToken extends Model
{
    use HasUuids;

    public const PREFIX = 'kmjmf_';

    protected $table = 'ai_model_tokens';

    /** @var list<string> */
    protected $guarded = [];

    /** @var list<string> */
    protected $hidden = ['token_hash'];

    /** @return array<string, string> */
    protected function casts(): array
    {
        return [
            'private_source' => 'boolean',
            'expires_at' => 'datetime',
            'last_used_at' => 'datetime',
            'revoked_at' => 'datetime',
        ];
    }

    public static function hash(string $plain): string
    {
        return hash('sha256', $plain);
    }

    public function isUsable(): bool
    {
        return $this->revoked_at === null && $this->expires_at->isFuture();
    }
}
