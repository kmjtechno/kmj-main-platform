<?php

namespace KMJ\MainPlatform\Releases\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasOne;

final class ProductRelease extends Model
{
    use HasUuids;

    protected $table = 'product_releases';

    protected $fillable = [
        'product_id',
        'version',
        'artifact_digest',
        'provenance_ref',
        'status',
        'promoted_at',
        'revoked_at',
    ];

    public function artifact(): HasOne
    {
        return $this->hasOne(ReleaseArtifact::class, 'release_id');
    }

    protected function casts(): array
    {
        return [
            'promoted_at' => 'immutable_datetime',
            'revoked_at' => 'immutable_datetime',
        ];
    }
}
