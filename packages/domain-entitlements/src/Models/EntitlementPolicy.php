<?php

namespace KMJ\MainPlatform\Entitlements\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;

final class EntitlementPolicy extends Model
{
    use HasUuids;

    protected $table = 'entitlement_policies';

    protected $fillable = [
        'product_id',
        'code',
        'capability',
        'status',
    ];
}
