<?php

declare(strict_types=1);

namespace App\Services\AiProviders;

use Illuminate\Http\Client\ConnectionException;
use Illuminate\Support\Facades\Http;
use InvalidArgumentException;

/**
 * OpenRouter's OAuth (PKCE) flow: the owner signs in to OpenRouter (Google, GitHub, ...) and
 * OpenRouter issues an API key for this app. No client secret is involved. The key is exchanged
 * server-side only, to the fixed host, and is never returned to the browser or logged.
 */
final class OpenRouterConnect
{
    private const AUTH_URL = 'https://openrouter.ai/auth';

    private const EXCHANGE_BASE = 'https://openrouter.ai/api/v1';

    public function __construct(private readonly EndpointGuard $guard) {}

    /** @return array{url: string, verifier: string} */
    public function begin(string $callbackUrl): array
    {
        if (! str_starts_with($callbackUrl, 'https://')) {
            throw new InvalidArgumentException('callback_not_https');
        }
        $verifier = self::base64Url(random_bytes(48));
        $challenge = self::base64Url(hash('sha256', $verifier, true));

        return [
            'url' => self::AUTH_URL.'?'.http_build_query([
                'callback_url' => $callbackUrl,
                'code_challenge' => $challenge,
                'code_challenge_method' => 'S256',
            ]),
            'verifier' => $verifier,
        ];
    }

    /** Exchange the one-time code (bound to our verifier) for an API key. */
    public function exchange(string $code, string $verifier): string
    {
        if (preg_match('/\A[A-Za-z0-9._~-]{8,256}\z/', $code) !== 1
            || preg_match('/\A[A-Za-z0-9_-]{43,128}\z/', $verifier) !== 1
            || ! defined('CURLOPT_RESOLVE')) {
            throw new InvalidArgumentException('oauth_invalid');
        }
        $target = $this->guard->validate(self::EXCHANGE_BASE, ['openrouter.ai']);

        try {
            $response = Http::withOptions([
                'allow_redirects' => false,
                'curl' => [CURLOPT_RESOLVE => [$target['host'].':443:'.$target['ip']]],
            ])->acceptJson()->asJson()->timeout(10)->connectTimeout(5)->post($target['base'].'/auth/keys', [
                'code' => $code,
                'code_verifier' => $verifier,
                'code_challenge_method' => 'S256',
            ]);
        } catch (ConnectionException) {
            throw new InvalidArgumentException('oauth_unreachable');
        }

        $key = $response->successful() ? $response->json('key') : null;
        if (! is_string($key) || preg_match('/\A[A-Za-z0-9_.-]{16,256}\z/', $key) !== 1) {
            throw new InvalidArgumentException('oauth_exchange_failed');
        }

        return $key;
    }

    private static function base64Url(string $bytes): string
    {
        return rtrim(strtr(base64_encode($bytes), '+/', '-_'), '=');
    }
}
