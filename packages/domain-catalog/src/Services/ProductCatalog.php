<?php

namespace KMJ\MainPlatform\Catalog\Services;

use DomainException;
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

    public function ensureCommercialProduct(string $slug, string $name): Product
    {
        $slug = trim($slug);
        $name = trim($name);

        if ($slug === '' || $name === '') {
            throw new InvalidArgumentException('Product slug and name are required.');
        }

        $product = Product::query()->firstOrCreate(
            ['slug' => $slug],
            [
                'name' => $name,
                'status' => 'active',
            ],
        );

        if (
            (string) $product->getAttribute('name') !== $name
            || (string) $product->getAttribute('status') !== 'active'
        ) {
            throw new DomainException('Product slug is already bound to different catalog facts.');
        }

        return $product;
    }
}
