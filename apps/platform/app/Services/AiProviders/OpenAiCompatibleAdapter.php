<?php

declare(strict_types=1);

namespace App\Services\AiProviders;

use Illuminate\Http\Client\ConnectionException;
use Illuminate\Support\Facades\Http;
use InvalidArgumentException;

/**
 * Read-only probe of an OpenAI-compatible API: GET {base}/models. OpenRouter alone
 * adds its documented max_price=0 catalog filter (admission still checks :free).
 * It never sends a prompt,
 * so a connection test cannot consume tokens or money. The key is sent only as a bearer
 * header to the pinned, validated address and is never placed in any result or error.
 */
final class OpenAiCompatibleAdapter
{
    private const MAX_MODELS = 200;

    private const MAX_BODY = 2_000_000;

    private const MAX_COMPLETION_TOKENS = 1024;

    private const MAX_CODING_TOKENS = 4096;

    private const MAX_CODING_CHARS = 32768;

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

        // OpenRouter's documented server-side filter reduces the catalog sent
        // to this fixed 2 MB / 200-ID reader. A zero prompt-price result is NOT
        // authorization for inference: only the existing :free rule admits it.
        $catalogUrl = $target['base'].'/models';
        if ($target['host'] === 'openrouter.ai') {
            $catalogUrl .= '?max_price=0';
        }
        // GitHub Models lists its catalog at a sibling path and returns a bare JSON list.
        $github = $target['host'] === 'models.github.ai';
        if ($github) {
            $catalogUrl = 'https://models.github.ai/catalog/models';
        }

        try {
            $response = Http::withOptions([
                'allow_redirects' => false,
                'curl' => [CURLOPT_RESOLVE => [$target['host'].':443:'.$target['ip']]],
            ])->withToken($apiKey)->acceptJson()->withHeaders($github ? ['Accept' => 'application/vnd.github+json', 'X-GitHub-Api-Version' => '2022-11-28'] : [])->timeout(10)->connectTimeout(5)->get($catalogUrl);
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

        $data = $github ? $response->json() : $response->json('data');
        if (! is_array($data) || ! array_is_list($data)) {
            // An HTTP 200 with an error payload is not a successful catalog.
            return $this->result('unreachable', [], $rate, $github ? $this->githubShapeCode($response->header('Content-Type'), $data, strlen($response->body())) : 'invalid_catalog');
        }

        // Some catalogs list paid models before free variants. Scan the
        // already size-limited response before applying the 200-ID cache cap.
        // Only OpenRouter suffix variants get priority. Other providers keep
        // the prior first-200 order; inference still requires FreePolicy.
        $free = [];
        $other = [];
        foreach ($data as $entry) {
            $id = is_array($entry) ? ($entry['id'] ?? null) : null;
            if (! is_string($id) || preg_match('/\A[A-Za-z0-9._:\/-]{1,128}\z/', $id) !== 1) {
                continue;
            }
            if ($target['host'] === 'openrouter.ai' && str_ends_with($id, ':free')) {
                $free[$id] = true;
            } else {
                $other[$id] = true;
            }
        }
        $models = array_slice(array_merge(array_keys($free), array_keys($other)), 0, self::MAX_MODELS);
        sort($models);

        return $this->result('ok', $models, $rate, null);
    }

    /**
     * One bounded, non-streaming chat completion. The CALLER must have passed the zero-spend
     * admission guard first. The key goes only to the pinned, validated address; the result
     * carries a content string or a short error code, never raw provider output.
     *
     * @param  list<string>  $approvedHosts
     * @param  list<array{role: string, content: string}>  $messages
     * @return array{ok: bool, content: ?string, error_code: ?string, rate?: array{requests_remaining: ?int, tokens_remaining: ?int, retry_after: ?int, daily_requests_limit?: int, daily_reset_seconds?: int}}
     */
    public function complete(string $baseUrl, string $apiKey, array $approvedHosts, string $model, array $messages, ?int $strictCodingTokens = null): array
    {
        if ($strictCodingTokens !== null && ($strictCodingTokens < 1 || $strictCodingTokens > self::MAX_CODING_TOKENS)) {
            return ['ok' => false, 'content' => null, 'error_code' => 'invalid_output_limit'];
        }
        try {
            $target = $this->guard->validate($baseUrl, $approvedHosts);
        } catch (InvalidArgumentException $exception) {
            return ['ok' => false, 'content' => null, 'error_code' => $exception->getMessage()];
        }
        if (! defined('CURLOPT_RESOLVE')) {
            return ['ok' => false, 'content' => null, 'error_code' => 'pinning_unavailable'];
        }

        $body = [
            'model' => $model,
            'messages' => $messages,
            'max_tokens' => $strictCodingTokens ?? self::MAX_COMPLETION_TOKENS,
            'stream' => false,
        ];
        if ($strictCodingTokens !== null) {
            // Independently verify this exact account and model before sending source.
            // Do not route unsupported providers through the general chat path.
            if (! (new NativeOpenRouterAdmission($this->guard))->verify($target['base'], $apiKey, $approvedHosts, $model)) {
                return ['ok' => false, 'content' => null, 'error_code' => 'native_account_unverified'];
            }
            $body['provider'] = [
                'allow_fallbacks' => false,
                'require_parameters' => true,
                'data_collection' => 'deny',
                'zdr' => true,
                'max_price' => ['prompt' => 0, 'completion' => 0, 'request' => 0, 'image' => 0],
            ];
        }

        try {
            $response = Http::withOptions([
                'allow_redirects' => false,
                'curl' => [CURLOPT_RESOLVE => [$target['host'].':443:'.$target['ip']]],
            ])->withToken($apiKey)->acceptJson()->timeout(45)->connectTimeout(5)->post($target['base'].'/chat/completions', $body);
        } catch (ConnectionException) {
            return ['ok' => false, 'content' => null, 'error_code' => 'connection_failed'];
        }

        $limit = $this->rateLimit($response->headers());
        $rate = [
            'requests_remaining' => $limit['requests_remaining'] ?? null,
            'tokens_remaining' => $limit['tokens_remaining'] ?? null,
            'retry_after' => $this->retryAfter($response->header('Retry-After')),
        ];
        // Only Groq's documented request headers are known to describe its daily window.
        if ($target['host'] === 'api.groq.com') {
            $total = $response->header('x-ratelimit-limit-requests');
            $reset = $this->dailyResetSeconds($response->header('x-ratelimit-reset-requests'));
            if (is_string($total) && preg_match('/\\A[1-9]\\d{0,8}\\z/', $total) === 1
                && $reset !== null && is_int($rate['requests_remaining']) && $rate['requests_remaining'] <= (int) $total) {
                $rate['daily_requests_limit'] = (int) $total;
                $rate['daily_reset_seconds'] = $reset;
            }
        }
        $fail = static fn (string $code): array => ['ok' => false, 'content' => null, 'error_code' => $code, 'rate' => $rate];

        $status = $response->status();
        if ($status === 401 || $status === 403) {
            return $fail('auth_failed');
        }
        if ($status === 429) {
            return $fail('rate_limited');
        }
        if ($status >= 300) {
            return $fail($status >= 500 ? 'provider_unavailable' : 'unexpected_status');
        }
        if (strlen($response->body()) > self::MAX_BODY) {
            return $fail('response_too_large');
        }
        $content = $response->json('choices.0.message.content');
        if (! is_string($content) || trim($content) === '') {
            return $fail('empty_response');
        }

        if ($strictCodingTokens !== null) {
            // A coding patch must not be silently clipped or marked complete after an interrupted reply.
            if ($response->json('choices.0.finish_reason') !== 'stop' || mb_strlen($content) > self::MAX_CODING_CHARS || str_contains($content, "\0")) {
                return $fail('incomplete_coding_output');
            }

            return ['ok' => true, 'content' => $content, 'error_code' => null, 'rate' => $rate];
        }

        return ['ok' => true, 'content' => mb_substr($content, 0, 8000), 'error_code' => null, 'rate' => $rate];
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

    /** Parse Groq's documented duration, e.g. 2m59.56s; reject ambiguous or excessive windows. */
    private function dailyResetSeconds(?string $value): ?int
    {
        if (! is_string($value) || preg_match('/\\A(?:(\\d{1,2})h)?(?:(\\d{1,2})m)?(?:(\\d{1,2}(?:\\.\\d{1,9})?)s)?\\z/', $value, $parts) !== 1 || $value === '') {
            return null;
        }
        $seconds = (int) ceil((int) ($parts[1] ?? 0) * 3600 + (int) ($parts[2] ?? 0) * 60 + (float) ($parts[3] ?? 0));

        return $seconds > 0 && $seconds <= 86400 ? $seconds : null;
    }

    private function retryAfter(?string $value): ?int
    {
        return is_string($value) && preg_match('/\A\d{1,6}\z/', $value) === 1 ? min(3600, max(1, (int) $value)) : null;
    }

    /**
     * Shape-only diagnostic for a GitHub catalog that is not a JSON list: content type, JSON type and key
     * names (never values or body text), cut to the 48-character error-code column.
     */
    private function githubShapeCode(string $contentType, mixed $data, int $length): string
    {
        $type = strtolower(explode(';', $contentType)[0]);
        $shape = is_array($data)
            ? 'obj:'.implode(',', array_slice(array_map('strval', array_keys($data)), 0, 3))
            : 'txt:'.$length;

        return substr('invalid_catalog:'.(string) preg_replace('/[^a-z0-9:,_+.\/|-]/', '', strtolower($type.'|'.$shape)), 0, 48);
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
