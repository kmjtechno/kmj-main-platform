<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

final class OperatorActionAudit extends Model
{
    protected $fillable = [
        'actor_user_id',
        'action',
        'outcome',
        'metadata',
    ];

    /** @return array<string, string> */
    protected function casts(): array
    {
        return [
            'actor_user_id' => 'integer',
            'metadata' => 'array',
        ];
    }
}
