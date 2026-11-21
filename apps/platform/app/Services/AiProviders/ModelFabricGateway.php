<?php

declare(strict_types=1);

namespace App\Services\AiProviders;

use App\Models\AiModelRequest;
use App\Models\AiProvider;
use Illuminate\Support\Facades\Cache;

/**
 * Failover over verified-zero routes only (design ideas adopted from the MIT-licensed FreeLLMAPI
 * project: cooldowns, bounded retries, per-provider circuit breaking). It only ever walks routes
 * that ModelFabricRouter admits, so a failover can never reach a paid or unknown-cost model, and
 * ProviderManager re-checks admission on every call. Only metadata is logged.
 */
final class ModelFabricGateway
{
    public const MAX_ATTEMPTS = 3;

    private const RATE_LIMIT_COOLDOWN = 60;

    private const SOFT_FAIL_COOLDOWN = 30;

    private const CIRCUIT_COOLDOWN = 300;

    private const AUTH_COOLDOWN = 3600;

    private const CIRCUIT_THRESHOLD = 3;

    public function __construct(
        private readonly ModelFabricRouter $router,
        private readonly ProviderManager $manager,
    ) {}

    /**
     * @param  list<array{role: string, content: string}>  $messages
     * @return array{ok: bool, content: ?string, error_code: ?string, provider: ?string, model: ?string, attempts: int}
     */
    public function complete(string $organizationId, array $messages, string $capability = 'chat', bool $privateSource = false): array
    {
        $plan = $this->router->plan($organizationId, $capability, $privateSource);
        if ($plan['status'] === ModelFabricRouter::NO_ROUTE) {
            return $this->fail(ModelFabricRouter::NO_ROUTE, 0);
        }

        $attempts = 0;
        $last = 'all_routes_cooling_down';
        foreach ($plan['routes'] as $route) {
            if ($attempts >= self::MAX_ATTEMPTS) {
                break;
            }
            $providerId = (string) $route['provider_id'];
            if (self::coolingUntil($providerId) !== null) {
                continue;
            }
            $provider = AiProvider::query()->where('organization_id', $organizationId)->whereKey($providerId)->first();
            if ($provider === null) {
                continue;
            }

            $attempts++;
            $started = hrtime(true);
            $result = $this->manager->complete($provider, (string) $route['model'], $messages);
            $latency = (int) ((hrtime(true) - $started) / 1_000_000);

            $this->record($organizationId, $provider, (string) $route['model'], $result['ok'], $result['error_code'], $latency);
            if ($result['ok']) {
                Cache::forget($this->failKey($providerId));

                return [
                    'ok' => true,
                    'content' => $result['content'],
                    'error_code' => null,
                    'provider' => $provider->name,
                    'model' => (string) $route['model'],
                    'attempts' => $attempts,
                ];
            }

            $last = (string) ($result['error_code'] ?? 'unknown');
            $this->penalize($provider, $last);
        }

        return $this->fail($last, $attempts);
    }

    /** Unix time until which the provider is skipped, or null when it may be used. */
    public static function coolingUntil(string $providerId): ?int
    {
        $until = Cache::get('modelfabric:cooldown:'.$providerId);

        return is_int($until) && $until > time() ? $until : null;
    }

    private function penalize(AiProvider $provider, string $code): void
    {
        $seconds = match ($code) {
            'rate_limited' => self::RATE_LIMIT_COOLDOWN,
            'auth_failed' => self::AUTH_COOLDOWN,
            'provider_unavailable', 'connection_failed', 'empty_response', 'unexpected_status', 'response_too_large' => $this->softFailure($provider->id),
            // Admission refusals (zero_spend_blocked, model_not_discovered, ...) are not provider faults.
            default => 0,
        };
        if ($code === 'auth_failed') {
            // A rejected key is not routed again until the owner re-tests the connection.
            $provider->health = 'auth_failed';
            $provider->last_error_code = 'auth_failed';
            $provider->save();
        }
        if ($seconds > 0) {
            Cache::put('modelfabric:cooldown:'.$provider->id, time() + $seconds, $seconds);
        }
    }

    private function softFailure(string $providerId): int
    {
        $failures = (int) Cache::get($this->failKey($providerId), 0) + 1;
        Cache::put($this->failKey($providerId), $failures, 900);

        return $failures >= self::CIRCUIT_THRESHOLD ? self::CIRCUIT_COOLDOWN : self::SOFT_FAIL_COOLDOWN;
    }

    private function record(string $organizationId, AiProvider $provider, string $model, bool $ok, ?string $code, int $latency): void
    {
        AiModelRequest::query()->create([
            'organization_id' => $organizationId,
            'ai_provider_id' => $provider->id,
            'model_id' => $model,
            'outcome' => $ok ? 'ok' : 'failed',
            'error_code' => $ok ? null : $code,
            'latency_ms' => max(0, $latency),
        ]);
    }

    private function failKey(string $providerId): string
    {
        return 'modelfabric:fail:'.$providerId;
    }

    /** @return array{ok: bool, content: ?string, error_code: ?string, provider: ?string, model: ?string, attempts: int} */
    private function fail(string $code, int $attempts): array
    {
        return ['ok' => false, 'content' => null, 'error_code' => $code, 'provider' => null, 'model' => null, 'attempts' => $attempts];
    }
}
