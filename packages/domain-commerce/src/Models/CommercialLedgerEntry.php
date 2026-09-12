<?php

namespace KMJ\MainPlatform\Commerce\Models;

use Illuminate\Database\Eloquent\Model;

final class CommercialLedgerEntry extends Model
{
    protected $table = 'commerce_ledger';

    protected $primaryKey = 'sequence';

    public $incrementing = true;

    public $timestamps = false;

    protected $fillable = [
        'order_id',
        'organization_id',
        'actor_user_id',
        'event_type',
        'payload',
        'occurred_at',
        'created_at',
    ];

    protected function casts(): array
    {
        return [
            'actor_user_id' => 'integer',
            'payload' => 'array',
            'occurred_at' => 'immutable_datetime',
            'created_at' => 'immutable_datetime',
        ];
    }
}
