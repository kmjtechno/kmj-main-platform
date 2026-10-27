<?php

namespace App\Services\ProductStudio;

use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Str;
use RuntimeException;

final class ProductArtworkStorage
{
    public function store(string $binary): string
    {
        if (strlen($binary) > 8 * 1024 * 1024) {
            throw new RuntimeException('Artwork must be 8 MB or smaller.');
        }
        $info = @getimagesizefromstring($binary);
        $extensions = ['image/png' => 'png', 'image/jpeg' => 'jpg', 'image/webp' => 'webp'];
        if ($info === false || ! isset($extensions[$info['mime']])
            || $info[0] < 1 || $info[1] < 1 || $info[0] > 4096 || $info[1] > 4096) {
            throw new RuntimeException('Use a valid PNG, JPEG or WebP image up to 4096 pixels per side.');
        }
        $name = Str::uuid().'.'.$extensions[$info['mime']];
        if (! Storage::disk('local')->put('product-artwork/'.$name, $binary)) {
            throw new RuntimeException('Artwork could not be saved.');
        }

        return '/product-artwork/'.$name;
    }
}
