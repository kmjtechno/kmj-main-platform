<?php

declare(strict_types=1);

namespace App\Services\AiProviders;

use App\Models\AiModelEvidence;
use App\Models\AiModelRequest;
use App\Models\AiProvider;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;
use InvalidArgumentException;
use RuntimeException;

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

    private const KILO_HOURLY_CAP = 200;

    private const KILO_COOLDOWN_KEY = 'modelfabric:kilo-free:shared-cooldown';

    private const SOFT_FAIL_COOLDOWN = 30;

    private const CIRCUIT_COOLDOWN = 300;

    private const AUTH_COOLDOWN = 3600;

    private const CIRCUIT_THRESHOLD = 3;

    private const STICKY_TTL = 1800;

    public function __construct(
        private readonly ModelFabricRouter $router,
        private readonly ProviderManager $manager,
        private readonly TaskProfiler $profiler,
        private readonly RouteScorer $scorer,
    ) {}

    /**
     * Preserve the workspace's explicit provider/model choice without bypassing
     * the shared gateway's admission, quota reservation and cooldown checks.
     *
     * @param  list<array{role: string, content: string}>  $messages
     * @return array{ok: bool, content: ?string, error_code: ?string, provider: ?string, model: ?string, attempts: int, profile: string}
     */
    public function completeSelected(AiProvider $provider, string $model, array $messages): array
    {
        try {
            $this->manager->assertInferenceAllowed($provider, $model);
        } catch (InvalidArgumentException|RuntimeException $exception) {
            return $this->fail($exception->getMessage(), 0, $this->profiler->classify($messages, 'chat'));
        }

        return $this->complete($provider->organization_id, $messages, selectedRoute: ['provider_id' => $provider->id, 'model' => $model]);
    }

    /**
     * @param  list<array{role: string, content: string}>  $messages
     * @param  array{provider_id: string, model: string}|null  $selectedRoute
     * @param  array{provider_id: string, model: string}|null  $nativeRoute
     * @return array{ok: bool, content: ?string, error_code: ?string, provider: ?string, model: ?string, attempts: int, profile: string}
     */
    public function complete(string $organizationId, array $messages, string $capability = 'chat', bool $privateSource = false, ?string $sessionKey = null, bool $strictFreeCloud = false, ?int $maxCodingTokens = null, ?array $nativeRoute = null, bool $publicPromptsConfirmed = false, ?array $selectedRoute = null): array
    {
        $profile = $this->profiler->classify($messages, $capability);
        if ($strictFreeCloud && ($capability !== 'code' || ! $privateSource || ($maxCodingTokens !== null && ($maxCodingTokens < 1 || $maxCodingTokens > 4096)))) {
            return $this->fail('invalid_coding_policy', 0, $profile);
        }
        $plan = $this->router->plan($organizationId, $capability, $privateSource, $strictFreeCloud, $publicPromptsConfirmed);
        if ($plan['status'] === ModelFabricRouter::NO_ROUTE) {
            return $this->fail(ModelFabricRouter::NO_ROUTE, 0, $profile);
        }
        if ($nativeRoute !== null) {
            if (! $strictFreeCloud) {
                return $this->fail('invalid_coding_policy', 0, $profile);
            }
            $plan['routes'] = array_values(array_filter($plan['routes'], static fn (array $route): bool => $route['provider_id'] === $nativeRoute['provider_id'] && $route['model'] === $nativeRoute['model']));
            if ($plan['routes'] === []) {
                return $this->fail(ModelFabricRouter::NO_ROUTE, 0, $profile);
            }
        }
        if ($selectedRoute !== null) {
            $plan['routes'] = array_values(array_filter($plan['routes'], static fn (array $route): bool => $route['provider_id'] === $selectedRoute['provider_id'] && $route['model'] === $selectedRoute['model']));
            if ($plan['routes'] === []) {
                return $this->fail(ModelFabricRouter::NO_ROUTE, 0, $profile);
            }
        }
        $limits = $this->providerLimits($organizationId);
        $plan['routes'] = $this->scorer->order($plan['routes'], $profile, fn (string $id, string $model): array => [
            'low' => $this->nearLimit($id, $model, (bool) ($limits[$id]['model_scoped'] ?? false)) || $this->nearDailyCap($limits[$id] ?? null),
            'fails' => (int) Cache::get($this->failKey($id), 0),
            'priority' => (int) ($limits[$id]['priority'] ?? 100),
        ]);

        // Count every local attempt against the most conservative current credit cap for a connection.
        // A request count is not a monetary balance. The provider's hard no-overage policy is still required.
        $creditUsed = $this->creditUsage($organizationId, $plan['routes']);
        // Sticky sessions are a preference only. Apply quota partitioning AFTER stickiness so
        // continuity and owner priority cannot keep sending work to a nearly exhausted route.
        $plan['routes'] = $this->preferSticky($plan['routes'], $organizationId, $sessionKey);
        $plan['routes'] = $this->sinkNearQuota($organizationId, $plan['routes'], $creditUsed, $limits);

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
            // A model-specific 429 should not disable other eligible models at the same provider.
            if ($this->modelCoolingUntil($providerId, (string) $route['model']) !== null) {
                $last = 'model_rate_limited';

                continue;
            }
            if ($this->dailyQuotaExhausted($providerId, (string) $route['model'], (bool) ($limits[$providerId]['model_scoped'] ?? false))) {
                $last = 'provider_daily_quota_exhausted';

                continue;
            }
            if (($route['cost_class'] ?? 'free') === 'credit-limited') {
                $cap = $this->sharedCreditCap($organizationId, $providerId, (int) ($route['credit_daily_cap'] ?? 0));
                if ($cap <= 0 || ($creditUsed[$providerId] ?? 0) >= $cap) {
                    $last = 'credit_cap_reached';

                    continue;
                }
            }
            // Owner's daily cap: skip before the provider's own limit can be hit.
            if (($limits[$providerId]['cap'] ?? null) !== null && $limits[$providerId]['used'] >= $limits[$providerId]['cap']) {
                $last = 'daily_cap_reached';

                continue;
            }
            // Reserve the attempt BEFORE the outbound request. A short database
            // transaction serializes reservations for the same provider, including
            // across PHP workers. A crash consumes the reservation conservatively.
            $reservation = $this->reserveAttempt($organizationId, $providerId, (string) $route['model'], $capability, $privateSource, $strictFreeCloud, $publicPromptsConfirmed);
            if ($reservation['error'] !== null) {
                $last = $reservation['error'];

                continue;
            }
            $provider = $reservation['provider'];
            $attempt = $reservation['attempt'];

            $attempts++;
            $started = hrtime(true);
            $result = $this->manager->complete($provider, (string) $route['model'], $messages, $strictFreeCloud ? ($maxCodingTokens ?? 1024) : null, $attempt, $publicPromptsConfirmed);
            $latency = (int) ((hrtime(true) - $started) / 1_000_000);

            $attempt->update([
                'outcome' => $result['ok'] ? 'ok' : 'failed',
                'error_code' => $result['ok'] ? null : $result['error_code'],
                'latency_ms' => max(0, $latency),
            ]);
            $this->learnLimits($providerId, (string) $route['model'], (bool) ($limits[$providerId]['model_scoped'] ?? false), $result['rate'] ?? null);
            if ($result['ok']) {
                Cache::forget($this->failKey($providerId));
                if ($sessionKey !== null) {
                    Cache::put($this->stickyKey($organizationId, $sessionKey), $providerId.'|'.(string) $route['model'], self::STICKY_TTL);
                }

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
            $this->penalize($provider, (string) $route['model'], $last, $result['rate'] ?? null);
        }

        return $this->fail($last, $attempts, $profile);
    }

    /**
     * Owner priority/cap plus today's routed attempts (UTC day) per provider of this organization.
     *
     * @return array<string, array{priority: int, cap: ?int, used: int, model_scoped: bool, keyless_near: bool}>
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
        foreach (AiProvider::query()->where('organization_id', $organizationId)->get(['id', 'preset', 'priority', 'daily_request_cap']) as $provider) {
            $out[$provider->id] = [
                'priority' => (int) $provider->priority,
                'cap' => $provider->daily_request_cap === null ? null : (int) $provider->daily_request_cap,
                'used' => (int) ($used[$provider->id] ?? 0),
                // Groq publishes per-model rate limits; unknown providers remain account-scoped.
                'model_scoped' => $provider->preset === 'groq',
                'keyless_near' => $provider->preset === 'kilo-free' && self::kiloHourlyUsage() >= 160,
            ];
        }

        return $out;
    }

    /**
     * Today's total routed attempts (UTC day) per connection, including non-credit models.
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
            ->selectRaw('ai_provider_id, count(*) as c')
            ->groupBy('ai_provider_id')
            ->toBase()
            ->get();
        foreach ($rows as $row) {
            $used[(string) $row->ai_provider_id] = (int) $row->c;
        }

        return $used;
    }

    /**
     * Stable partition: prefer healthy quota headroom, including owner daily caps and provider-reported model/account limits.
     *
     * @param  list<array<string, mixed>>  $routes
     * @param  array<string, int>  $creditUsed
     * @param  array<string, array{priority: int, cap: ?int, used: int, model_scoped: bool, keyless_near: bool}>  $limits
     * @return list<array<string, mixed>>
     */
    private function sinkNearQuota(string $organizationId, array $routes, array $creditUsed, array $limits): array
    {
        $normal = [];
        $near = [];
        foreach ($routes as $route) {
            $providerId = (string) $route['provider_id'];
            $cap = ($route['cost_class'] ?? 'free') === 'credit-limited'
                ? $this->sharedCreditCap($organizationId, $providerId, (int) ($route['credit_daily_cap'] ?? 0)) : 0;
            $used = $creditUsed[$providerId] ?? 0;
            $limit = $limits[$providerId] ?? null;
            $nearCreditCap = ($route['cost_class'] ?? 'free') === 'credit-limited' && $cap > 0 && $used * 10 >= $cap * 8;
            if ($nearCreditCap || ($limit['keyless_near'] ?? false) || $this->nearDailyCap($limit)
                || $this->nearLimit($providerId, (string) $route['model'], (bool) ($limit['model_scoped'] ?? false))) {
                $near[] = $route;
            } else {
                $normal[] = $route;
            }
        }

        return [...$normal, ...$near];
    }

    private function stickyKey(string $organizationId, string $sessionKey): string
    {
        return 'modelfabric:sticky:'.hash('sha256', $organizationId.'|'.$sessionKey);
    }

    /**
     * @param  list<array<string, mixed>>  $routes
     * @return list<array<string, mixed>>
     */
    private function preferSticky(array $routes, string $organizationId, ?string $sessionKey): array
    {
        if ($sessionKey === null) {
            return $routes;
        }
        $last = Cache::get($this->stickyKey($organizationId, $sessionKey));
        if (! is_string($last)) {
            return $routes;
        }
        $first = [];
        $rest = [];
        foreach ($routes as $route) {
            if ($last === $route['provider_id'].'|'.$route['model']) {
                $first[] = $route;
            } else {
                $rest[] = $route;
            }
        }

        return [...$first, ...$rest];
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
     * @param  array{requests_remaining: ?int, tokens_remaining: ?int, retry_after: ?int, daily_requests_limit?: int, daily_reset_seconds?: int}|null  $rate
     */
    private function learnLimits(string $providerId, string $model, bool $modelScoped, ?array $rate): void
    {
        if ($rate === null || ($rate['requests_remaining'] === null && $rate['tokens_remaining'] === null)) {
            return;
        }
        // Groq's documented RPD window is independent of the short-lived TPM signal.
        // Never infer a daily reset for providers with undocumented header semantics.
        $dailyLimit = $rate['daily_requests_limit'] ?? null;
        $reset = $rate['daily_reset_seconds'] ?? null;
        if ($modelScoped && is_int($dailyLimit) && $dailyLimit > 0
            && is_int($reset) && $reset > 0 && $reset <= 86400
            && is_int($rate['requests_remaining']) && $rate['requests_remaining'] >= 0 && $rate['requests_remaining'] <= $dailyLimit) {
            Cache::put($this->dailyRateKey($providerId, $model), [
                'remaining' => $rate['requests_remaining'],
                'limit' => $dailyLimit,
                'reset_at' => now()->addSeconds($reset)->toIso8601String(),
            ], $reset);
        }
        $key = $this->rateKey($providerId, $model, $modelScoped);
        $seen = Cache::get($key);
        $maxRequests = max((int) ($rate['requests_remaining'] ?? 0), is_array($seen) ? (int) ($seen['max_requests'] ?? 0) : 0);
        Cache::put($key, [
            'requests' => $rate['requests_remaining'],
            'tokens' => $rate['tokens_remaining'],
            'max_requests' => $maxRequests,
            'observed_at' => now()->toIso8601String(),
        ], 120);
    }

    /**
     * Actual recent provider response headers only, not account billing credits or predicted quota.
     * Unknown, expired and unobserved values must stay unknown in the UI.
     *
     * @param list<string> $models
     * @return list<array<string, mixed>>
     */
    public function quotaObservations(AiProvider $provider, array $models): array
    {
        $modelScoped = $provider->preset === 'groq';
        $observations = [];
        foreach (array_slice($modelScoped ? $models : ['shared across models'], 0, 12) as $model) {
            $observed = Cache::get($this->rateKey($provider->id, $model, $modelScoped));
            $daily = $modelScoped ? Cache::get($this->dailyRateKey($provider->id, $model)) : null;
            if (! is_array($observed) && ! is_array($daily)) {
                continue;
            }
            $observations[] = [
                'model' => $model,
                'scope' => $modelScoped ? 'model' : 'provider',
                'requests_remaining' => is_array($observed) && is_int($observed['requests'] ?? null) ? $observed['requests'] : null,
                'tokens_remaining' => is_array($observed) && is_int($observed['tokens'] ?? null) ? $observed['tokens'] : null,
                'observed_at' => is_array($observed) ? ($observed['observed_at'] ?? null) : null,
                'daily_remaining' => is_array($daily) && is_int($daily['remaining'] ?? null) ? $daily['remaining'] : null,
                'daily_limit' => is_array($daily) && is_int($daily['limit'] ?? null) ? $daily['limit'] : null,
                'daily_reset_at' => is_array($daily) ? ($daily['reset_at'] ?? null) : null,
            ];
        }

        return $observations;
    }

    private function nearLimit(string $providerId, string $model, bool $modelScoped): bool
    {
        $daily = $modelScoped ? Cache::get($this->dailyRateKey($providerId, $model)) : null;
        if (is_array($daily) && $daily['limit'] >= $daily['remaining'] * 5) {
            return true;
        }
        $seen = Cache::get($this->rateKey($providerId, $model, $modelScoped));
        if (! is_array($seen)) {
            return false;
        }
        $requests = $seen['requests'] ?? null;
        $max = (int) ($seen['max_requests'] ?? 0);
        $tokens = $seen['tokens'] ?? null;
        $lowRequests = is_int($requests) && ($requests <= 2 || ($max >= 20 && $requests * 10 <= $max));

        return $lowRequests || (is_int($tokens) && $tokens <= 2000);
    }

    /** @param array{requests_remaining: ?int, tokens_remaining: ?int, retry_after: ?int, daily_requests_limit?: int, daily_reset_seconds?: int}|null $rate */
    private function penalize(AiProvider $provider, string $model, string $code, ?array $rate = null): void
    {
        $retryAfter = $rate['retry_after'] ?? null;
        if ($code === 'rate_limited' && $provider->preset === 'kilo-free') {
            // All anonymous Kilo requests share the same Elite egress-IP quota.
            $seconds = max(60, min(3600, $retryAfter ?? 3600));
            Cache::put(self::KILO_COOLDOWN_KEY, true, $seconds);
        }
        // A verified Groq model's exhausted quota must not cool the entire provider.
        // Without a typed remaining=0 report, conservatively use provider-wide cooldown.
        if ($code === 'rate_limited' && $provider->preset === 'groq' && ($rate['requests_remaining'] ?? null) === 0) {
            $seconds = $retryAfter !== null ? max(5, min(300, $retryAfter)) : self::RATE_LIMIT_COOLDOWN;
            Cache::put($this->modelCooldownKey($provider->id, $model), time() + $seconds, $seconds);

            return;
        }
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

    private function rateKey(string $providerId, string $model, bool $modelScoped): string
    {
        return 'modelfabric:rate:'.($modelScoped ? hash('sha256', $providerId.'|'.$model) : $providerId);
    }

    private function dailyRateKey(string $providerId, string $model): string
    {
        return 'modelfabric:daily-rate:'.hash('sha256', $providerId.'|'.$model);
    }

    private function dailyQuotaExhausted(string $providerId, string $model, bool $modelScoped): bool
    {
        $daily = $modelScoped ? Cache::get($this->dailyRateKey($providerId, $model)) : null;

        return is_array($daily) && ($daily['remaining'] ?? null) === 0;
    }

    private function modelCooldownKey(string $providerId, string $model): string
    {
        return 'modelfabric:model-cooldown:'.hash('sha256', $providerId.'|'.$model);
    }

    private function modelCoolingUntil(string $providerId, string $model): ?int
    {
        $until = Cache::get($this->modelCooldownKey($providerId, $model));

        return is_int($until) && $until > time() ? $until : null;
    }

    private function softFailure(string $providerId): int
    {
        $failures = (int) Cache::get($this->failKey($providerId), 0) + 1;
        Cache::put($this->failKey($providerId), $failures, 900);

        return $failures >= self::CIRCUIT_THRESHOLD ? self::CIRCUIT_COOLDOWN : self::SOFT_FAIL_COOLDOWN;
    }

    /**
     * @return array{provider: ?AiProvider, attempt: ?AiModelRequest, error: ?string}
     */
    private function reserveAttempt(string $organizationId, string $providerId, string $model, string $capability, bool $privateSource, bool $strictFreeCloud, bool $publicPromptsConfirmed): array
    {
        return DB::transaction(function () use ($organizationId, $providerId, $model, $capability, $privateSource, $strictFreeCloud, $publicPromptsConfirmed): array {
            $deny = static fn (string $code): array => ['provider' => null, 'attempt' => null, 'error' => $code];
            $provider = AiProvider::query()->where('organization_id', $organizationId)->whereKey($providerId)->lockForUpdate()->first();
            if ($provider === null) {
                return $deny('provider_unavailable');
            }

            if ($provider->preset === 'kilo-free') {
                // Serialize all Kilo reservations across organizations on the production PostgreSQL database.
                $driver = DB::connection()->getDriverName();
                if ($driver === 'pgsql') {
                    DB::select('SELECT pg_advisory_xact_lock(1263356999)');
                } elseif ($driver !== 'sqlite') {
                    return $deny('shared_quota_unavailable');
                }
                if (Cache::has(self::KILO_COOLDOWN_KEY) || self::kiloHourlyUsage() >= self::KILO_HOURLY_CAP) {
                    return $deny('keyless_hourly_quota_exhausted');
                }
            }

            // Re-evaluate the current plan under the reservation lock. Never
            // reserve a previously admitted but now revoked or expired route.
            $current = null;
            foreach ($this->router->plan($organizationId, $capability, $privateSource, $strictFreeCloud, $publicPromptsConfirmed)['routes'] as $candidate) {
                if ($candidate['provider_id'] === $providerId && $candidate['model'] === $model) {
                    $current = $candidate;
                    break;
                }
            }
            if ($current === null) {
                return $deny(ModelFabricRouter::NO_ROUTE);
            }
            if (self::coolingUntil($providerId) !== null || $this->modelCoolingUntil($providerId, $model) !== null) {
                return $deny('all_routes_cooling_down');
            }

            if ($this->dailyQuotaExhausted($providerId, $model, $provider->preset === 'groq')) {
                return $deny('provider_daily_quota_exhausted');
            }

            $today = AiModelRequest::query()
                ->where('organization_id', $organizationId)
                ->where('ai_provider_id', $providerId)
                ->where('created_at', '>=', now()->utc()->startOfDay());
            if ($provider->daily_request_cap !== null && (clone $today)->count() >= (int) $provider->daily_request_cap) {
                return $deny('daily_cap_reached');
            }
            if (($current['cost_class'] ?? 'free') === 'credit-limited') {
                $cap = $this->sharedCreditCap($organizationId, $providerId, (int) ($current['credit_daily_cap'] ?? 0));
                if ($cap <= 0 || (clone $today)->count() >= $cap) {
                    return $deny('credit_cap_reached');
                }
            }

            // Metadata only. Failed or interrupted reservations count against
            // the cap; never release an ambiguous upstream attempt automatically.
            $attempt = AiModelRequest::query()->create([
                'organization_id' => $organizationId,
                'ai_provider_id' => $providerId,
                'model_id' => $model,
                'outcome' => 'failed',
                'error_code' => 'attempt_reserved',
                'latency_ms' => 0,
            ]);

            if ($provider->preset === 'kilo-free') {
                // Keep the shared IP budget independent of provider or tenant deletion.
                // Both rows commit under the same PostgreSQL advisory lock.
                DB::table('ai_shared_quota_reservations')->insert([
                    'id' => $attempt->id,
                    'scope' => 'kilo-free',
                    'created_at' => now(),
                ]);
                DB::table('ai_shared_quota_reservations')->where('scope', 'kilo-free')
                    ->where('created_at', '<', now()->subHours(2))->delete();
            }

            return ['provider' => $provider, 'attempt' => $attempt, 'error' => null];
        });
    }

    private function sharedCreditCap(string $organizationId, string $providerId, int $routeCap): int
    {
        if ($routeCap <= 0) {
            return 0;
        }

        $cap = $routeCap;
        foreach (AiModelEvidence::query()->where('organization_id', $organizationId)
            ->where('ai_provider_id', $providerId)->where('cost_class', 'credit-limited')
            ->whereNull('revoked_at')->where('expires_at', '>', now())->get() as $proof) {
            if ($proof->credit_hard_cap_attested_at === null || $proof->credit_daily_cap === null || $proof->credit_daily_cap <= 0) {
                return 0;
            }
            $cap = min($cap, $proof->credit_daily_cap);
        }

        return $cap;
    }

    /** @return array{used: int, limit: int, cooling: bool} */
    public static function kiloQuotaSnapshot(): array
    {
        return [
            'used' => self::kiloHourlyUsage(),
            'limit' => self::KILO_HOURLY_CAP,
            'cooling' => Cache::has(self::KILO_COOLDOWN_KEY),
        ];
    }

    private static function kiloHourlyUsage(): int
    {
        $since = now()->subHour();
        $ledger = DB::table('ai_shared_quota_reservations')->where('scope', 'kilo-free');
        // Count any pre-ledger history once, without double-counting new reservations.
        $legacy = AiModelRequest::query()
            ->whereIn('ai_provider_id', AiProvider::query()->select('id')->where('preset', 'kilo-free'))
            ->whereNotIn('id', (clone $ledger)->select('id'))
            ->where('created_at', '>=', $since)
            ->count();

        return $legacy + (clone $ledger)->where('created_at', '>=', $since)->count();
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
