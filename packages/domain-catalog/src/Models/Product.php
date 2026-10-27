<?php

namespace KMJ\MainPlatform\Catalog\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;

final class Product extends Model
{
    use HasUuids;

    protected $table = 'products';

    protected $fillable = [
        'slug',
        'name',
        'status',
        'lifecycle',
        'category',
        'is_public',
        'sort_order',
        'image_path',
        'summary',
        'content',
        'purchase_enabled',
        'licensing_enabled',
    ];

    protected function casts(): array
    {
        return [
            'content' => 'array',
            'is_public' => 'boolean',
            'purchase_enabled' => 'boolean',
            'licensing_enabled' => 'boolean',
            'sort_order' => 'integer',
        ];
    }
}
