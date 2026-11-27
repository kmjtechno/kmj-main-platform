<?php

declare(strict_types=1);

namespace App\Services\AiProviders;

use App\Models\AiModelToken;
use App\Models\AiProvider;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Str;

/**
 * Read-only upstream verification followed by a short-lived single-use dispatch ticket.
 * Tickets bind the authenticated token, request digest and one exact provider/model.
 * No prompts, provider secrets or raw provider response are stored.
 */
final class NativeCodingAdmissionTicket
{
    private const TTL = 25;

    private const MAX_CANDIDATES = 3;

    public function __construct(
        private readonly ModelFabricRouter $router,
        private readonly ProviderManager $manager,
        private readonly NativeOpenRouterAdmission $admission,
        private readonly ModelFabricGateway $gateway,
    ) {}

    /** @return array<string, mixed>|null */
    public function issue(AiModelToken $token, string $digest): ?array
    {
        if (! $token->private_source || ! $token->isUsable() || preg_match('/\A[a-f0-9]{64}\z/', $digest) !== 1) {
            return null;
        }
        $routes = $this->router->plan($token->organization_id, 'code', true, true)['routes'];
        $attempted = 0;
        foreach ($routes as $route) {
            $provider = AiProvider::query()->where('organization_id', $token->organization_id)->whereKey($route['provider_id'])->first();
            if ($provider === null || $provider->preset !== 'openrouter'
                || ! $this->gateway->nativePreflightAllowed($provider, (string) $route['model'])) {
                continue;
            }
            if (++$attempted > self::MAX_CANDIDATES) {
                break;
            }
            $model = (string) $route['model'];
            $remaining = $this->admission->remainingRequests($provider->base_url, $provider->api_key, $this->manager->approvedHosts(), $model);
            if ($remaining <= 0 || ! $token->fresh()?->isUsable()) {
                continue;
            }
            $ticket = Str::random(64);
            $issued = (int) floor(microtime(true) * 1000);
            Cache::put($this->key($ticket), [
                'token_id' => $token->id,
                'digest' => $digest,
                'provider_id' => $provider->id,
                'model' => $model,
                'expires_at' => $issued + self::TTL * 1000,
            ], self::TTL);

            return [
                'source' => 'kmj_native_provider_admission',
                'request_digest' => $digest,
                'ticket' => $ticket,
                'requests_remaining' => $remaining,
                'issued_at_ms' => $issued,
                'expires_at_ms' => $issued + self::TTL * 1000,
            ];
        }

        return null;
    }

    /** @return array{provider_id: string, model: string}|null */
    public function consume(AiModelToken $token, string $ticket, string $digest): ?array
    {
        if (preg_match('/\A[A-Za-z0-9]{64}\z/', $ticket) !== 1 || preg_match('/\A[a-f0-9]{64}\z/', $digest) !== 1) {
            return null;
        }
        $key = $this->key($ticket);

        return Cache::lock($key.':lock', 10)->get(function () use ($key, $token, $digest): ?array {
            $entry = Cache::get($key);
            if (! is_array($entry) || ($entry['token_id'] ?? null) !== $token->id
                || ! is_string($entry['digest'] ?? null) || ! hash_equals($entry['digest'], $digest)
                || ! is_int($entry['expires_at'] ?? null) || $entry['expires_at'] <= (int) floor(microtime(true) * 1000)
                || ! is_string($entry['provider_id'] ?? null) || ! is_string($entry['model'] ?? null)
                // Middleware's token object can be stale if an owner revoked
                // the token during the upstream read-only ticket preflight.
                // Re-read the exact token row within the consume lock.
                || ! $token->fresh()?->isUsable()) {
                return null;
            }
            Cache::forget($key);

            return ['provider_id' => $entry['provider_id'], 'model' => $entry['model']];
        }) ?: null;
    }

    private function key(string $ticket): string
    {
        return 'modelfabric:native-ticket:'.hash('sha256', $ticket);
    }
}
