<?php

namespace KMJ\MainPlatform\Catalog\Services;

use DomainException;
use InvalidArgumentException;
use KMJ\MainPlatform\Catalog\Models\Product;

final class ProductCatalog
{
    public function ensureSandboxProduct(string $slug, string $name): Product
    {
        return $this->ensureProduct($slug, $name, 'sandbox');
    }

    public function ensureCommercialProduct(string $slug, string $name): Product
    {
        return $this->ensureProduct($slug, $name, 'active');
    }

    private function ensureProduct(string $slug, string $name, string $status): Product
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
                'status' => $status,
            ],
        );

        if ((string) $product->name !== $name || (string) $product->status !== $status) {
            throw new DomainException('Product slug is already bound to different catalog facts.');
        }

        return $product;
    }
}
