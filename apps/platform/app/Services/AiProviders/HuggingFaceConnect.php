<?php

declare(strict_types=1);

namespace App\Services\AiProviders;

use Illuminate\Http\Client\ConnectionException;
use Illuminate\Support\Facades\Http;
use InvalidArgumentException;

/**
 * Hugging Face "Sign in with HF" (OAuth 2.0 authorization code + PKCE, public client, no secret).
 * The client is identified by a metadata document served from this site (HF's documented CIMD flow),
 * so the owner registers nothing by hand. Only the `inference-api` scope is requested. The access
 * token is exchanged server-side to the fixed host and is never returned to the browser or logged.
 */
final class HuggingFaceConnect
{
    private const AUTH_URL = 'https://huggingface.co/oauth/authorize';

    private const EXCHANGE_BASE = 'https://huggingface.co';

    public const SCOPE = 'inference-api';

    public function __construct(private readonly EndpointGuard $guard) {}

    /** @return array{client_id: string, client_name: string, redirect_uris: list<string>, token_endpoint_auth_method: string} */
    public function metadata(string $clientId, string $redirectUri): array
    {
        return [
            'client_id' => $clientId,
            'client_name' => 'KMJ TECHNO ModelFabric',
            'redirect_uris' => [$redirectUri],
            'token_endpoint_auth_method' => 'none',
        ];
    }

    /** @return array{url: string, verifier: string, state: string} */
    public function begin(string $clientId, string $redirectUri): array
    {
        if (! str_starts_with($clientId, 'https://') || ! str_starts_with($redirectUri, 'https://')) {
            throw new InvalidArgumentException('callback_not_https');
        }
        $verifier = self::base64Url(random_bytes(48));
        $state = self::base64Url(random_bytes(32));

        return [
            'url' => self::AUTH_URL.'?'.http_build_query([
                'client_id' => $clientId,
                'redirect_uri' => $redirectUri,
                'scope' => self::SCOPE,
                'state' => $state,
                'response_type' => 'code',
                'code_challenge' => self::base64Url(hash('sha256', $verifier, true)),
                'code_challenge_method' => 'S256',
            ]),
            'verifier' => $verifier,
            'state' => $state,
        ];
    }

    /** Exchange the one-time code (bound to our verifier) for an access token. */
    public function exchange(string $code, string $verifier, string $clientId, string $redirectUri): string
    {
        if (preg_match('/\A[A-Za-z0-9._~-]{8,512}\z/', $code) !== 1
            || preg_match('/\A[A-Za-z0-9_-]{43,128}\z/', $verifier) !== 1
            || ! defined('CURLOPT_RESOLVE')) {
            throw new InvalidArgumentException('oauth_invalid');
        }
        $target = $this->guard->validate(self::EXCHANGE_BASE, ['huggingface.co']);

        try {
            $response = Http::withOptions([
                'allow_redirects' => false,
                'curl' => [CURLOPT_RESOLVE => [$target['host'].':443:'.$target['ip']]],
            ])->acceptJson()->asForm()->timeout(10)->connectTimeout(5)->post($target['base'].'/oauth/token', [
                'grant_type' => 'authorization_code',
                'code' => $code,
                'redirect_uri' => $redirectUri,
                'client_id' => $clientId,
                'code_verifier' => $verifier,
            ]);
        } catch (ConnectionException) {
            throw new InvalidArgumentException('oauth_unreachable');
        }

        $token = $response->successful() ? $response->json('access_token') : null;
        if (! is_string($token) || preg_match('/\A[A-Za-z0-9_.-]{16,512}\z/', $token) !== 1) {
            throw new InvalidArgumentException('oauth_exchange_failed');
        }

        return $token;
    }

    private static function base64Url(string $bytes): string
    {
        return rtrim(strtr(base64_encode($bytes), '+/', '-_'), '=');
    }
}
