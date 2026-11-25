<?php

declare(strict_types=1);

namespace App\Services\AiProviders;

use Illuminate\Http\Client\ConnectionException;
use Illuminate\Support\Facades\Http;
use InvalidArgumentException;

/**
 * Initial native account admission implementation: exact OpenRouter free variant,
 * authenticated quota and current catalog evidence. No provider inference occurs here.
 * Unsupported providers remain unverified, not presumed free.
 */
final class NativeOpenRouterAdmission
{
    private const BASE = 'https://openrouter.ai/api/v1';

    public function __construct(private readonly EndpointGuard $guard) {}

    /** @param list<string> $approvedHosts */
    public function verify(string $baseUrl, string $apiKey, array $approvedHosts, string $model): bool
    {
        return $this->remainingRequests($baseUrl, $apiKey, $approvedHosts, $model) > 0;
    }

    /** @param list<string> $approvedHosts */
    public function remainingRequests(string $baseUrl, string $apiKey, array $approvedHosts, string $model): int
    {
        if ($baseUrl !== self::BASE || ! self::validModel($model) || ! defined('CURLOPT_RESOLVE')) {
            return 0;
        }

        try {
            $target = $this->guard->validate(self::BASE, $approvedHosts);
            $client = Http::withOptions([
                'allow_redirects' => false,
                'curl' => [CURLOPT_RESOLVE => [$target['host'].':443:'.$target['ip']]],
            ])->withToken($apiKey)->acceptJson()->timeout(10)->connectTimeout(5);
            $key = $client->get(self::BASE.'/key');
            if ($key->status() !== 200 || strlen($key->body()) > 65536 || ! self::accountEligible($key->json('data'))) {
                return 0;
            }
            $catalog = $client->get(self::BASE.'/models', ['max_price' => 0]);
            if ($catalog->status() !== 200 || strlen($catalog->body()) > 8000000) {
                return 0;
            }

            return self::modelEligible($catalog->json('data'), $model) ? (int) $key->json('data.free_model_daily_requests.remaining') : 0;
        } catch (ConnectionException|InvalidArgumentException) {
            return 0;
        }
    }

    public static function accountEligible(mixed $account): bool
    {
        if (! is_array($account) || ($account['is_free_tier'] ?? null) !== true
            || ($account['is_management_key'] ?? null) !== false || ($account['is_provisioning_key'] ?? null) !== false) {
            return false;
        }
        foreach (['usage', 'usage_daily', 'usage_weekly', 'usage_monthly', 'byok_usage', 'byok_usage_daily', 'byok_usage_weekly', 'byok_usage_monthly'] as $field) {
            if (! in_array($account[$field] ?? null, [0, 0.0], true)) {
                return false;
            }
        }
        // Not a guaranteed field of the documented /key contract. Absent provider-reported
        // quota must remain unavailable, not be inferred from the published daily plan limit.
        $quota = $account['free_model_daily_requests'] ?? null;
        if (! is_array($quota) || ! is_int($quota['limit'] ?? null) || ! is_int($quota['used'] ?? null) || ! is_int($quota['remaining'] ?? null)) {
            return false;
        }

        return $quota['limit'] > 0 && $quota['used'] >= 0 && $quota['remaining'] > 0
            && $quota['used'] <= $quota['limit'] && $quota['remaining'] <= $quota['limit'] - $quota['used'];
    }

    public static function modelEligible(mixed $catalog, string $model): bool
    {
        if (! self::validModel($model) || ! is_array($catalog) || ! array_is_list($catalog) || count($catalog) > 5000) {
            return false;
        }
        $matches = 0;
        foreach ($catalog as $row) {
            if (! is_array($row) || ($row['id'] ?? null) !== $model) {
                continue;
            }
            $matches++;
            $price = $row['pricing'] ?? null;
            if (! is_array($price) || ! self::zeroPrice($price['prompt'] ?? null) || ! self::zeroPrice($price['completion'] ?? null)) {
                return false;
            }
            foreach ($price as $value) {
                if (! self::zeroPrice($value)) {
                    return false;
                }
            }
        }

        return $matches === 1;
    }

    private static function zeroPrice(mixed $value): bool
    {
        return is_string($value) && preg_match('/\A0(?:\.0+)?\z/', $value) === 1;
    }

    private static function validModel(string $model): bool
    {
        return preg_match('/\A[a-z0-9][a-z0-9._-]{0,62}\/[A-Za-z0-9][A-Za-z0-9._-]{0,80}:free\z/', $model) === 1;
    }
}
