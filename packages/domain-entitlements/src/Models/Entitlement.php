<?php

namespace KMJ\MainPlatform\Entitlements\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;

final class Entitlement extends Model
{
    use HasUuids;

    protected $table = 'entitlements';

    protected $fillable = [
        'organization_id',
        'product_id',
        'policy_id',
        'capability',
        'status',
        'idempotency_key',
        'starts_at',
        'ends_at',
    ];

    protected function casts(): array
    {
        return [
            'starts_at' => 'immutable_datetime',
            'ends_at' => 'immutable_datetime',
        ];
    }
}
