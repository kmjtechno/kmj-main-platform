<?php

declare(strict_types=1);

namespace App\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;

/**
 * One routed attempt. Metadata only: no prompt, response or credential is ever stored.
 *
 * @property string $id
 * @property string $organization_id
 * @property string $ai_provider_id
 * @property string $model_id
 * @property string $outcome
 * @property string|null $error_code
 * @property int $latency_ms
 */
final class AiModelRequest extends Model
{
    use HasUuids;

    public const UPDATED_AT = null;

    protected $table = 'ai_model_requests';

    /** @var list<string> */
    protected $guarded = [];
}
