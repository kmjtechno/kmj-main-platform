<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

final class LicenseAuditEvent extends Model
{
    /** @var list<string> */
    protected $fillable = [
        'actor_id',
        'organization_id',
        'action',
        'jti',
        'status',
        'metadata',
    ];

    /**
     * @return array<string, string>
     */
    protected function casts(): array
    {
        return [
            'metadata' => 'array',
        ];
    }
}
