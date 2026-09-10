<?php

namespace KMJ\MainPlatform\Organizations\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

final class Organization extends Model
{
    use HasUuids;

    protected $table = 'organizations';

    protected $fillable = [
        'name',
    ];

    public function memberships(): HasMany
    {
        return $this->hasMany(OrganizationMembership::class);
    }
}
