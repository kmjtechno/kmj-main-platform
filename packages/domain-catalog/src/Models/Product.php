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
    ];
}
