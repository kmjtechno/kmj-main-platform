<?php

namespace KMJ\MainPlatform\Releases\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

final class ReleaseArtifact extends Model
{
    use HasUuids;

    protected $table = 'release_artifacts';

    protected $fillable = [
        'release_id',
        'filename',
        'disk',
        'path',
        'media_type',
        'size_bytes',
        'digest',
    ];

    public function release(): BelongsTo
    {
        return $this->belongsTo(ProductRelease::class, 'release_id');
    }

    protected function casts(): array
    {
        return ['size_bytes' => 'integer'];
    }
}
