<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

final class LicenseRevocation extends Model
{
    protected $fillable = [
        'jti',
        'reason',
        'revoked_at',
    ];

    protected function casts(): array
    {
        return [
            'revoked_at' => 'immutable_datetime',
        ];
    }
}
