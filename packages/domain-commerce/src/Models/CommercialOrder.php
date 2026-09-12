<?php

namespace KMJ\MainPlatform\Commerce\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;

final class CommercialOrder extends Model
{
    use HasUuids;

    protected $table = 'commerce_orders';

    protected $fillable = [
        'organization_id',
        'product_id',
        'requester_user_id',
        'status',
        'idempotency_key',
        'currency',
        'amount_minor',
        'confirmation_reference',
        'confirmed_at',
        'cancelled_at',
    ];

    protected function casts(): array
    {
        return [
            'requester_user_id' => 'integer',
            'amount_minor' => 'integer',
            'confirmed_at' => 'immutable_datetime',
            'cancelled_at' => 'immutable_datetime',
        ];
    }
}
