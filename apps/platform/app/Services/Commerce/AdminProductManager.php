<?php

namespace App\Services\Commerce;

use DomainException;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\Rule;
use KMJ\MainPlatform\Catalog\Models\Product;

final class AdminProductManager
{
    public const LIFECYCLES = ['available', 'preview', 'public-beta', 'research', 'planned', 'retired'];

    /**
     * @return array<string, mixed>
     */
    public static function rules(?Product $product = null, bool $partial = false): array
    {
        $presence = $partial ? 'sometimes' : 'required';

        return [
            'slug' => [$presence, 'string', 'max:96', 'regex:/^[a-z0-9]+(?:-[a-z0-9]+)*$/', Rule::unique('products', 'slug')->ignore($product?->getKey())],
            'name' => [$presence, 'string', 'min:2', 'max:160'],
            'lifecycle' => [$presence, Rule::in(self::LIFECYCLES)],
            'is_public' => [$presence, 'boolean'],
            'image_path' => ['sometimes', 'nullable', 'string', 'max:255'],
            'summary' => ['sometimes', 'nullable', 'string', 'max:2000'],
            'purchase_enabled' => [$presence, 'boolean'],
            'licensing_enabled' => [$presence, 'boolean'],
        ];
    }

    /**
     * @param  array<string, mixed>  $attributes
     */
    public function create(array $attributes): Product
    {
        return DB::transaction(function () use ($attributes): Product {
            $attributes['status'] ??= 'sandbox';
            $attributes['lifecycle'] ??= 'planned';
            $attributes['sort_order'] ??= ((int) Product::query()->max('sort_order')) + 10;

            $attributes = $this->normalized($attributes);
            $this->assertCommercialState($attributes);

            return Product::query()->create($attributes);
        });
    }

    /**
     * @param  array<string, mixed>  $attributes
     */
    public function update(Product $product, array $attributes): Product
    {
        $attributes = $this->normalized($attributes);
        $resultingState = [
            'lifecycle' => $attributes['lifecycle'] ?? $product->getAttribute('lifecycle'),
            'purchase_enabled' => $attributes['purchase_enabled'] ?? $product->getAttribute('purchase_enabled'),
        ];
        $this->assertCommercialState($resultingState);

        $product->fill($attributes);
        $product->save();

        return $product->refresh();
    }

    /**
     * @param  array<array-key, string>  $ids
     */
    public function reorder(array $ids): void
    {
        DB::transaction(function () use ($ids): void {
            if (count($ids) !== count(array_unique($ids))) {
                throw new DomainException('Product ordering contains duplicate products.');
            }

            $products = Product::query()->whereIn('id', $ids)->get()->keyBy(fn (Product $p) => (string) $p->getKey());
            if ($products->count() !== count($ids)) {
                throw new DomainException('Product ordering contains unknown products.');
            }

            if (Product::query()->count() !== count($ids)) {
                throw new DomainException('Product ordering must include the complete catalog.');
            }

            foreach (array_values($ids) as $index => $id) {
                $products->get($id)->forceFill(['sort_order' => ($index + 1) * 10])->save();
            }
        });
    }

    /**
     * @param  array<string, mixed>  $attributes
     * @return array<string, mixed>
     */
    /**
     * @param  array<string, mixed>  $attributes
     */
    private function assertCommercialState(array $attributes): void
    {
        if (
            (bool) ($attributes['purchase_enabled'] ?? false)
            && ($attributes['lifecycle'] ?? null) !== 'available'
        ) {
            throw new DomainException('Purchase can only be enabled for an available product.');
        }
    }

    private function normalized(array $attributes): array
    {
        if (isset($attributes['lifecycle']) && ! in_array($attributes['lifecycle'], self::LIFECYCLES, true)) {
            throw new DomainException('Unsupported product lifecycle.');
        }
        foreach (['is_public', 'purchase_enabled', 'licensing_enabled'] as $key) {
            if (array_key_exists($key, $attributes)) {
                $attributes[$key] = (bool) $attributes[$key];
            }
        }

        return $attributes;
    }
}
