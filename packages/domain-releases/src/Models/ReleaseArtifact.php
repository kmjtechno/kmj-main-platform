<?php

namespace KMJ\MainPlatform\Releases\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

/**
 * @property string $release_id
 * @property string $filename
 * @property string $disk
 * @property string $path
 * @property string|null $media_type
 * @property int $size_bytes
 * @property string $digest
 * @property-read ProductRelease $release
 */
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
