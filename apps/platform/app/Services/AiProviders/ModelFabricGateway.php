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
        private readonly TaskProfiler $profiler,
        private readonly RouteScorer $scorer,
    ) {}

    /**
     * @param  list<array{role: string, content: string}>  $messages
     * @return array{ok: bool, content: ?string, error_code: ?string, provider: ?string, model: ?string, attempts: int, profile: string}
     */
    public function complete(string $organizationId, array $messages, string $capability = 'chat', bool $privateSource = false): array
    {
        $profile = $this->profiler->classify($messages, $capability);
        $plan = $this->router->plan($organizationId, $capability, $privateSource);
        if ($plan['status'] === ModelFabricRouter::NO_ROUTE) {
            return $this->fail(ModelFabricRouter::NO_ROUTE, 0, $profile);
        }
        $limits = $this->providerLimits($organizationId);
        $plan['routes'] = $this->scorer->order($plan['routes'], $profile, fn (string $id): array => [
            'low' => $this->nearLimit($id) || $this->nearDailyCap($limits[$id] ?? null),
            'fails' => (int) Cache::get($this->failKey($id), 0),
            'priority' => (int) ($limits[$id]['priority'] ?? 100),
        ]);

        // ADR-004 rev 2: a credit-limited route is skipped at its owner-set daily cap and sinks at 80%, so
        // a mis-stated provider limit can never spend the owner's money. A missing or zero cap fails closed.
        $creditUsed = $this->creditUsage($organizationId, $plan['routes']);
        $plan['routes'] = $this->sinkNearCreditCap($plan['routes'], $creditUsed);

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
            if (($route['cost_class'] ?? 'free') === 'credit-limited') {
                $cap = (int) ($route['credit_daily_cap'] ?? 0);
                if ($cap <= 0 || ($creditUsed[$providerId.'|'.(string) $route['model']] ?? 0) >= $cap) {
                    $last = 'credit_cap_reached';

                    continue;
                }
            }
            // Owner's daily cap: skip before the provider's own limit can be hit.
            if (($limits[$providerId]['cap'] ?? null) !== null && $limits[$providerId]['used'] >= $limits[$providerId]['cap']) {
                $last = 'daily_cap_reached';

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
            $this->learnLimits($providerId, $result['rate'] ?? null);
            if ($result['ok']) {
                Cache::forget($this->failKey($providerId));

                return [
                    'ok' => true,
                    'content' => $result['content'],
                    'error_code' => null,
                    'provider' => $provider->name,
                    'model' => (string) $route['model'],
                    'attempts' => $attempts,
                    'profile' => $profile,
                ];
            }

            $last = (string) ($result['error_code'] ?? 'unknown');
            $this->penalize($provider, $last, $result['rate']['retry_after'] ?? null);
        }

        return $this->fail($last, $attempts, $profile);
    }

    /**
     * Owner priority/cap plus today's routed attempts (UTC day) per provider of this organization.
     *
     * @return array<string, array{priority: int, cap: ?int, used: int}>
     */
    private function providerLimits(string $organizationId): array
    {
        $used = AiModelRequest::query()
            ->where('organization_id', $organizationId)
            ->where('created_at', '>=', now()->utc()->startOfDay())
            ->selectRaw('ai_provider_id, count(*) as c')
            ->groupBy('ai_provider_id')
            ->pluck('c', 'ai_provider_id');

        $out = [];
        foreach (AiProvider::query()->where('organization_id', $organizationId)->get(['id', 'priority', 'daily_request_cap']) as $provider) {
            $out[$provider->id] = [
                'priority' => (int) $provider->priority,
                'cap' => $provider->daily_request_cap === null ? null : (int) $provider->daily_request_cap,
                'used' => (int) ($used[$provider->id] ?? 0),
            ];
        }

        return $out;
    }

    /**
     * Today's routed attempts (UTC day) per "provider|model" for credit-limited routes only.
     *
     * @param  list<array<string, mixed>>  $routes
     * @return array<string, int>
     */
    private function creditUsage(string $organizationId, array $routes): array
    {
        $providerIds = [];
        foreach ($routes as $route) {
            if (($route['cost_class'] ?? 'free') === 'credit-limited') {
                $providerIds[(string) $route['provider_id']] = true;
            }
        }
        if ($providerIds === []) {
            return [];
        }

        $used = [];
        $rows = AiModelRequest::query()
            ->where('organization_id', $organizationId)
            ->whereIn('ai_provider_id', array_keys($providerIds))
            ->where('created_at', '>=', now()->utc()->startOfDay())
            ->selectRaw('ai_provider_id, model_id, count(*) as c')
            ->groupBy('ai_provider_id', 'model_id')
            ->toBase()
            ->get();
        foreach ($rows as $row) {
            $used[(string) $row->ai_provider_id.'|'.(string) $row->model_id] = (int) $row->c;
        }

        return $used;
    }

    /**
     * Stable partition: credit-limited routes at or above 80% of their cap go last.
     *
     * @param  list<array<string, mixed>>  $routes
     * @param  array<string, int>  $creditUsed
     * @return list<array<string, mixed>>
     */
    private function sinkNearCreditCap(array $routes, array $creditUsed): array
    {
        $normal = [];
        $near = [];
        foreach ($routes as $route) {
            $cap = (int) ($route['credit_daily_cap'] ?? 0);
            $used = $creditUsed[(string) $route['provider_id'].'|'.(string) $route['model']] ?? 0;
            if (($route['cost_class'] ?? 'free') === 'credit-limited' && $cap > 0 && $used * 10 >= $cap * 8) {
                $near[] = $route;
            } else {
                $normal[] = $route;
            }
        }

        return [...$normal, ...$near];
    }

    /** @param  array{priority: int, cap: ?int, used: int}|null  $limit */
    private function nearDailyCap(?array $limit): bool
    {
        return $limit !== null && $limit['cap'] !== null && $limit['cap'] > 0 && $limit['used'] * 10 >= $limit['cap'] * 8;
    }

    /** Unix time until which the provider is skipped, or null when it may be used. */
    public static function coolingUntil(string $providerId): ?int
    {
        $until = Cache::get('modelfabric:cooldown:'.$providerId);

        return is_int($until) && $until > time() ? $until : null;
    }

    /**
     * Pre-emptive shift: remember the provider's own remaining-quota headers for a short window so the
     * scorer moves work away BEFORE the limit is hit. Counts come only from what the provider reports.
     *
     * @param  array{requests_remaining: ?int, tokens_remaining: ?int, retry_after: ?int}|null  $rate
     */
    private function learnLimits(string $providerId, ?array $rate): void
    {
        if ($rate === null || ($rate['requests_remaining'] === null && $rate['tokens_remaining'] === null)) {
            return;
        }
        $key = 'modelfabric:rate:'.$providerId;
        $seen = Cache::get($key);
        $maxRequests = max((int) ($rate['requests_remaining'] ?? 0), is_array($seen) ? (int) ($seen['max_requests'] ?? 0) : 0);
        Cache::put($key, [
            'requests' => $rate['requests_remaining'],
            'tokens' => $rate['tokens_remaining'],
            'max_requests' => $maxRequests,
        ], 120);
    }

    private function nearLimit(string $providerId): bool
    {
        $seen = Cache::get('modelfabric:rate:'.$providerId);
        if (! is_array($seen)) {
            return false;
        }
        $requests = $seen['requests'] ?? null;
        $max = (int) ($seen['max_requests'] ?? 0);
        $tokens = $seen['tokens'] ?? null;
        $lowRequests = is_int($requests) && ($requests <= 2 || ($max >= 20 && $requests * 10 <= $max));

        return $lowRequests || (is_int($tokens) && $tokens <= 2000);
    }

    private function penalize(AiProvider $provider, string $code, ?int $retryAfter = null): void
    {
        $seconds = match ($code) {
            'rate_limited' => $retryAfter !== null ? max(5, min(300, $retryAfter)) : self::RATE_LIMIT_COOLDOWN,
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

    /** @return array{ok: bool, content: ?string, error_code: ?string, provider: ?string, model: ?string, attempts: int, profile: string} */
    private function fail(string $code, int $attempts, string $profile): array
    {
        return ['ok' => false, 'content' => null, 'error_code' => $code, 'provider' => null, 'model' => null, 'attempts' => $attempts, 'profile' => $profile];
    }
}
