<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

final class DomainOutboxConsumption extends Model
{
    /** @var list<string> */
    protected $fillable = [
        'message_id',
        'consumer',
        'consumed_at',
    ];

    protected function casts(): array
    {
        return [
            'consumed_at' => 'immutable_datetime',
        ];
    }
}
