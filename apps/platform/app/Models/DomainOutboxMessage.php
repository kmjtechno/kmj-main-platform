<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

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
