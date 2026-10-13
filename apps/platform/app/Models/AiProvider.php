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
 * @property string $name
 * @property string $preset
 * @property string $kind
 * @property string $base_url
 * @property string $api_key
 * @property string|null $key_last4
 * @property bool $enabled
 * @property bool $free_only
 * @property string|null $default_model
 * @property array<int, mixed>|null $fallback_models
 * @property array<int, string>|null $models_cache
 * @property CarbonInterface|null $models_checked_at
 * @property string $health
 * @property CarbonInterface|null $health_checked_at
 * @property string|null $last_error_code
 * @property array<string, mixed>|null $rate_limit
 * @property int|null $created_by
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
