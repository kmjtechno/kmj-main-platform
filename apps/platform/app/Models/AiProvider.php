<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;

/**
 * @property string $id
 * @property string $organization_id
 */
final class AiProvider extends Model
{
    use HasUuids;

    protected $table = 'ai_providers';

    /** @var list<string> */
    protected $guarded = [];

    /** @var list<string> */
    protected $hidden = ['api_key'];

    /** @return array<string, string> */
    protected function casts(): array
    {
        return [
            'api_key' => 'encrypted',
            'enabled' => 'boolean',
            'free_only' => 'boolean',
            'fallback_models' => 'array',
            'models_cache' => 'array',
            'rate_limit' => 'array',
            'models_checked_at' => 'datetime',
            'health_checked_at' => 'datetime',
        ];
    }
}
