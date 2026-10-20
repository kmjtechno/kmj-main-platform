<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

final class CustomerProfile extends Model
{
    protected $fillable = [
        'user_id',
        'account_type',
        'phone',
        'country',
        'company_name',
        'service_interest',
    ];

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }
}
