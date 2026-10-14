<?php

declare(strict_types=1);

namespace App\Services\AiProviders;

use Illuminate\Http\Client\ConnectionException;
use Illuminate\Support\Facades\Http;
use InvalidArgumentException;

/**
 * Read-only probe of an OpenAI-compatible API: GET {base}/models. It never sends a prompt,
 * so a connection test cannot consume tokens or money. The key is sent only as a bearer
 * header to the pinned, validated address and is never placed in any result or error.
 */
final class OpenAiCompatibleAdapter
{
    private const MAX_MODELS = 200;

    private const MAX_BODY = 2_000_000;

    public function __construct(private readonly EndpointGuard $guard) {}

    /**
     * @param  list<string>  $approvedHosts
     * @return array{health: string, models: list<string>, rate_limit: array<string, mixed>, error_code: ?string, retry_after: ?int}
     */
    public function probe(string $baseUrl, string $apiKey, array $approvedHosts): array
    {
        try {
            $target = $this->guard->validate($baseUrl, $approvedHosts);
        } catch (InvalidArgumentException $exception) {
            return $this->result('blocked', [], [], $exception->getMessage());
        }

        if (! defined('CURLOPT_RESOLVE')) {
            // Without cURL the connection cannot be pinned to the validated address.
            return $this->result('blocked', [], [], 'pinning_unavailable');
        }

        try {
            $response = Http::withOptions([
                'allow_redirects' => false,
                'curl' => [CURLOPT_RESOLVE => [$target['host'].':443:'.$target['ip']]],
            ])->withToken($apiKey)->acceptJson()->timeout(10)->connectTimeout(5)->get($target['base'].'/models');
        } catch (ConnectionException) {
            return $this->result('unreachable', [], [], 'connection_failed');
        }

        $rate = $this->rateLimit($response->headers());
        $status = $response->status();
        if ($status === 401 || $status === 403) {
            return $this->result('auth_failed', [], $rate, 'auth_failed');
        }
        if ($status === 429) {
            return $this->result('rate_limited', [], $rate, 'rate_limited', $this->retryAfter($response->header('Retry-After')));
        }
        if ($status >= 300) {
            return $this->result('unreachable', [], $rate, $status >= 500 ? 'provider_unavailable' : 'unexpected_status');
        }
        if (strlen($response->body()) > self::MAX_BODY) {
            return $this->result('unreachable', [], $rate, 'response_too_large');
        }

        // OpenRouter may list hundreds of paid IDs before any :free model.
        // Scan the already size-bounded response before applying the 200-ID
        // storage cap, so late free candidates are not silently omitted.
        $free = [];
        $other = [];
        foreach ((array) ($response->json('data') ?? []) as $entry) {
            $id = is_array($entry) ? ($entry['id'] ?? null) : null;
            if (is_string($id) && preg_match('/\A[A-Za-z0-9._:\/-]{1,128}\z/', $id) === 1) {
                if (str_ends_with($id, ':free')) {
                    $free[] = $id;
                } else {
                    $other[] = $id;
                }
            }
        }
        $models = array_slice(array_values(array_unique([...$free, ...$other])), 0, self::MAX_MODELS);
        sort($models);

        return $this->result('ok', $models, $rate, null);
    }

    /**
     * Only counts the provider actually reports are "verified"; everything else stays unknown.
     *
     * @param  array<string, array<int, string>>  $headers
     * @return array<string, mixed>
     */
    private function rateLimit(array $headers): array
    {
        $headers = array_change_key_case($headers, CASE_LOWER);
        $number = static function (string $name) use ($headers): ?int {
            $value = $headers[$name][0] ?? null;

            return is_string($value) && preg_match('/\A\d{1,12}\z/', $value) === 1 ? (int) $value : null;
        };
        $requests = $number('x-ratelimit-remaining-requests');
        $tokens = $number('x-ratelimit-remaining-tokens');

        return [
            'status' => $requests !== null || $tokens !== null ? 'verified' : 'unknown',
            'requests_remaining' => $requests,
            'tokens_remaining' => $tokens,
        ];
    }

    private function retryAfter(?string $value): ?int
    {
        return is_string($value) && preg_match('/\A\d{1,6}\z/', $value) === 1 ? min(3600, max(1, (int) $value)) : null;
    }

    /**
     * @param  list<string>  $models
     * @param  array<string, mixed>  $rate
     * @return array{health: string, models: list<string>, rate_limit: array<string, mixed>, error_code: ?string, retry_after: ?int}
     */
    private function result(string $health, array $models, array $rate, ?string $code, ?int $retryAfter = null): array
    {
        return [
            'health' => $health,
            'models' => $models,
            'rate_limit' => $rate === [] ? ['status' => 'unknown', 'requests_remaining' => null, 'tokens_remaining' => null] : $rate,
            'error_code' => $code,
            'retry_after' => $retryAfter,
        ];
    }
}
