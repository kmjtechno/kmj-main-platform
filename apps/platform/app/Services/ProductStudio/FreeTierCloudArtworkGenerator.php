<?php

namespace App\Services\ProductStudio;

use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Http;
use RuntimeException;

/**
 * Optional Cloudflare Workers FREE-plan image adapter.
 * A Workers Paid account can charge for overage, so this adapter fails closed
 * unless the owner independently confirms the Workers Free plan. No fallback.
 */
final class FreeTierCloudArtworkGenerator
{
    private const ORIGIN = 'https://api.cloudflare.com/client/v4/accounts/';
    private const MODEL = '/ai/run/@cf/black-forest-labs/flux-1-schnell';

    public function generate(string $prompt, string $variant): string
    {
        if (config('product_studio.image.enabled') !== true
            || config('product_studio.image.free_account_attested') !== true
            || ! preg_match('/^[a-f0-9]{32}$/D', (string) config('product_studio.image.account_id', ''))
            || trim((string) config('product_studio.image.api_token', '')) === '') {
            throw new RuntimeException('FREE_IMAGE_ACCOUNT_NOT_VERIFIED');
        }
        if (! in_array($variant, ['photo', 'banner'], true)
            || mb_strlen($prompt) < 8 || mb_strlen($prompt) > 1500) {
            throw new RuntimeException('INVALID_IMAGE_REQUEST');
        }

        // Reserve a conservative maximum of two attempts in the daily shared
        // budget. No retry, paid fallback or automatic second image.
        // Free Workers plans cannot overrun the account's free allocation.
        $lock = Cache::lock('kmj-product-free-image-attempts-lock', 90);
        if (! $lock->get()) {
            throw new RuntimeException('FREE_IMAGE_BUSY');
        }
        try {
            $key = 'kmj-product-free-image-attempts:'.gmdate('Ymd');
            $attempts = (int) Cache::get($key, 0);
            $limit = min(2, max(0, (int) config('product_studio.image.max_daily_requests', 0)));
            if ($limit === 0 || $attempts >= $limit) {
                throw new RuntimeException('FREE_IMAGE_DAILY_LIMIT');
            }
            Cache::put($key, $attempts + 1, now()->addDay());
        } finally {
            $lock->release();
        }

        $scene = trim($prompt).' '.($variant === 'banner'
            ? 'Wide cinematic composition with negative space for typography added later.'
            : 'High-detail product-focused composition, clean lighting and realistic depth.')
            .' Illustrative visualization only. No words, logos, watermarks, '
            .'fake application screenshots or technical performance claims.';
        $scene = mb_substr($scene, 0, 2048);

        // Fixed official endpoint, fixed image model, no redirects or retries.
        $response = Http::timeout(85)->connectTimeout(3)->withoutRedirecting()
            ->withToken((string) config('product_studio.image.api_token'))
            ->post(self::ORIGIN.config('product_studio.image.account_id').self::MODEL, [
                'prompt' => $scene,
                'steps' => 4,
            ]);
        if (! $response->successful() || strlen($response->body()) > 11 * 1024 * 1024
            || $response->json('success') !== true) {
            throw new RuntimeException('FREE_IMAGE_PROVIDER_UNAVAILABLE');
        }
        $image = $response->json('result.image');
        if (! is_string($image) || strlen($image) > 11 * 1024 * 1024) {
            throw new RuntimeException('FREE_IMAGE_INVALID_RESPONSE');
        }
        $binary = base64_decode($image, true);
        if (! is_string($binary) || strlen($binary) > 8 * 1024 * 1024) {
            throw new RuntimeException('FREE_IMAGE_INVALID_BINARY');
        }

        // ProductArtworkStorage independently validates the mime, actual
        // dimensions and image bytes before attaching to an owner draft.
        return $binary;
    }
}
