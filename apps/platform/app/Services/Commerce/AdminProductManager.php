<?php

namespace App\Services\Commerce;

use DomainException;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\Rule;
use KMJ\MainPlatform\Catalog\Models\Product;

final class AdminProductManager
{
    public const LIFECYCLES = ['available', 'preview', 'public-beta', 'research', 'planned', 'retired'];

    public const CATEGORIES = ['cloud', 'cinema', 'industrial', 'developer', 'business', 'other'];

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
            'category' => ['sometimes', Rule::in(self::CATEGORIES)],
            'is_public' => [$presence, 'boolean'],
            'image_path' => ['sometimes', 'nullable', 'string', 'max:255'],
            'summary' => ['sometimes', 'nullable', 'string', 'max:2000'],
            ...self::contentRules(),
            'purchase_enabled' => [$presence, 'boolean'],
            'licensing_enabled' => [$presence, 'boolean'],
        ];
    }

    /** @return array<string, mixed> */
    public static function contentRules(): array
    {
        return [
            'content' => ['sometimes', 'nullable', 'array:headline,description,features,faqs,photo_prompt,banner_prompt,banner_path,image_alt'],
            'content.headline' => ['sometimes', 'nullable', 'string', 'max:200'],
            'content.description' => ['sometimes', 'nullable', 'string', 'max:20000'],
            'content.features' => ['sometimes', 'array', 'max:12'],
            'content.features.*' => ['string', 'max:500'],
            'content.faqs' => ['sometimes', 'array', 'max:8'],
            'content.faqs.*' => ['array:question,answer'],
            'content.faqs.*.question' => ['required', 'string', 'max:300'],
            'content.faqs.*.answer' => ['required', 'string', 'max:2000'],
            'content.photo_prompt' => ['sometimes', 'nullable', 'string', 'max:2000'],
            'content.banner_prompt' => ['sometimes', 'nullable', 'string', 'max:2000'],
            'content.banner_path' => ['sometimes', 'nullable', 'string', 'max:255', 'regex:#^/(?:assets/|product-artwork/)[a-zA-Z0-9_./-]+$#'],
            'content.image_alt' => ['sometimes', 'nullable', 'string', 'max:300'],
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
            $attributes['category'] ??= 'other';
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

    /**
     * @param  array<string, mixed>  $attributes
     * @return array<string, mixed>
     */
    private function normalized(array $attributes): array
    {
        if (isset($attributes['lifecycle']) && ! in_array($attributes['lifecycle'], self::LIFECYCLES, true)) {
            throw new DomainException('Unsupported product lifecycle.');
        }
        if (isset($attributes['category']) && ! in_array($attributes['category'], self::CATEGORIES, true)) {
            throw new DomainException('Unsupported product category.');
        }
        if (isset($attributes['content']) && is_array($attributes['content'])) {
            foreach (['headline', 'description', 'photo_prompt', 'banner_prompt', 'banner_path', 'image_alt'] as $field) {
                if (array_key_exists($field, $attributes['content']) && $attributes['content'][$field] === null) {
                    $attributes['content'][$field] = '';
                }
            }
        }
        foreach (['is_public', 'purchase_enabled', 'licensing_enabled'] as $key) {
            if (array_key_exists($key, $attributes)) {
                $attributes[$key] = (bool) $attributes[$key];
            }
        }

        return $attributes;
    }
}
