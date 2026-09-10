<?php

namespace KMJ\MainPlatform\Catalog\Services;

use InvalidArgumentException;
use KMJ\MainPlatform\Catalog\Models\Product;

final class ProductCatalog
{
    public function ensureSandboxProduct(string $slug, string $name): Product
    {
        $slug = trim($slug);
        $name = trim($name);

        if ($slug === '' || $name === '') {
            throw new InvalidArgumentException('Product slug and name are required.');
        }

        return Product::query()->firstOrCreate(
            ['slug' => $slug],
            [
                'name' => $name,
                'status' => 'sandbox',
            ],
        );
    }
}
