<?php

namespace KMJ\MainPlatform\Entitlements\Models;

use Illuminate\Database\Eloquent\Model;

final class EntitlementLedgerEntry extends Model
{
    public $incrementing = true;
    public $timestamps = false;

    protected $table = 'entitlement_ledger';
    protected $primaryKey = 'sequence';
    protected $keyType = 'int';

    protected $fillable = [
        'entitlement_id',
        'organization_id',
        'event_type',
        'payload',
        'occurred_at',
    ];

    protected function casts(): array
    {
        return [
            'payload' => 'array',
            'occurred_at' => 'immutable_datetime',
            'created_at' => 'immutable_datetime',
        ];
    }
}
