<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

/**
 * @property string $id
 * @property string $event_type
 * @property string $aggregate_type
 * @property string $aggregate_id
 * @property string|null $organization_id
 * @property int $attempts
 * @property string|null $last_error
 * @property \Carbon\CarbonImmutable|null $occurred_at
 * @property \Carbon\CarbonImmutable|null $published_at
 * @property \Carbon\CarbonImmutable|null $next_attempt_at
 * @property \Illuminate\Support\Carbon|null $created_at
 * @property \Illuminate\Support\Carbon|null $updated_at
 */
final class DomainOutboxMessage extends Model
{
    protected $table = 'outbox_messages';

    public $incrementing = false;

    protected $keyType = 'string';

    /** @var list<string> */
    protected $fillable = [
        'id',
        'event_type',
        'aggregate_type',
        'aggregate_id',
        'organization_id',
        'idempotency_key',
        'payload',
        'occurred_at',
        'published_at',
        'attempts',
        'last_error',
        'next_attempt_at',
    ];

    protected function casts(): array
    {
        return [
            'payload' => 'array',
            'occurred_at' => 'immutable_datetime',
            'published_at' => 'immutable_datetime',
            'attempts' => 'integer',
            'next_attempt_at' => 'immutable_datetime',
        ];
    }
}
