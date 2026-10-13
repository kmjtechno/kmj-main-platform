<?php

declare(strict_types=1);

namespace App\Services\AiProviders;

use App\Models\AiProvider;
use Illuminate\Support\Facades\Config;
use InvalidArgumentException;

final class ProviderManager
{
    private const DISCOVERY_MAX_AGE_HOURS = 24;

    public function __construct(
        private readonly OpenAiCompatibleAdapter $adapter,
        private readonly EndpointGuard $guard,
    ) {}

    /** @return array<string, array{label: string, base_url: ?string, free_tier: string}> */
    public function presets(): array
    {
        return Config::get('ai_providers.presets', []);
    }

    /** @return list<string> */
    public function approvedHosts(): array
    {
        $hosts = Config::get('ai_providers.approved_hosts', []);
        foreach ($this->presets() as $preset) {
            if (is_string($preset['base_url'])) {
                $hosts[] = (string) parse_url($preset['base_url'], PHP_URL_HOST);
            }
        }

        return array_values(array_unique(array_map('strtolower', $hosts)));
    }

    /** @param array<string, mixed> $data name, preset, api_key, optional base_url and free_only */
    public function create(string $organizationId, int $userId, array $data): AiProvider
    {
        $presetKey = (string) ($data['preset'] ?? '');
        $preset = $this->presets()[$presetKey] ?? throw new InvalidArgumentException('preset_unknown');
        $baseUrl = $preset['base_url'] ?? ($data['base_url'] ?? null);
        if (! is_string($baseUrl) || $baseUrl === '') {
            throw new InvalidArgumentException('endpoint_scheme');
        }
        $this->guard->validate($baseUrl, $this->approvedHosts());
        $apiKey = (string) ($data['api_key'] ?? '');

        return AiProvider::query()->create([
            'organization_id' => $organizationId,
            'name' => (string) ($data['name'] ?? ''),
            'preset' => $presetKey,
            'kind' => 'openai-compatible',
            'base_url' => $baseUrl,
            'api_key' => $apiKey,
            'key_last4' => substr($apiKey, -4),
            'free_only' => true,
            'created_by' => $userId,
        ]);
    }

    /** @param array<string, mixed> $data */
    public function update(AiProvider $provider, array $data): AiProvider
    {
        if (isset($data['api_key']) && is_string($data['api_key']) && $data['api_key'] !== '') {
            $provider->api_key = $data['api_key'];
            $provider->key_last4 = substr($data['api_key'], -4);
            // A replaced key invalidates earlier health and model evidence.
            $provider->health = 'unknown';
            $provider->models_cache = null;
            $provider->default_model = null;
            $provider->fallback_models = [];
        }
        foreach (['name', 'enabled'] as $field) {
            if (array_key_exists($field, $data)) {
                $provider->{$field} = $data[$field];
            }
        }
        if (array_key_exists('default_model', $data) || array_key_exists('fallback_models', $data)) {
            $known = $provider->models_cache ?? [];
            $default = array_key_exists('default_model', $data) ? $data['default_model'] : $provider->default_model;
            $fallbacks = array_values(array_unique((array) ($data['fallback_models'] ?? $provider->fallback_models ?? [])));
            $fallbacks = array_values(array_filter($fallbacks, static fn ($model): bool => $model !== $default));
            if (($default !== null && ! in_array($default, $known, true))
                || array_diff($fallbacks, $known) !== []
                || count($fallbacks) > 5) {
                throw new InvalidArgumentException('model_not_discovered');
            }
            $provider->default_model = $default;
            $provider->fallback_models = $fallbacks;
        }
        $provider->save();

        return $provider;
    }

    public function test(AiProvider $provider): AiProvider
    {
        $result = $this->adapter->probe($provider->base_url, $provider->api_key, $this->approvedHosts());
        $provider->health = $result['health'];
        $provider->health_checked_at = now();
        $provider->last_error_code = $result['error_code'];
        $provider->rate_limit = $result['rate_limit'] + ['retry_after' => $result['retry_after']];
        if ($result['health'] === 'ok') {
            $provider->models_cache = $result['models'];
            $provider->models_checked_at = now();
        }
        $provider->save();

        return $provider;
    }

    public function delete(AiProvider $provider): void
    {
        // Deleting the row removes the encrypted key; there is no soft-deleted copy.
        $provider->delete();
    }

    /**
     * Admission guard: routing must call this before ANY request that could be billed. It never
     * contacts the provider. A successful GET /models is only a health probe, not pricing
     * authorization. The provider must be enabled and healthy, the model must come from a recent
     * discovery (stale or spoofed ids are refused), and the model must pass the free rule.
     * There is no paid override here.
     */
    public function assertInferenceAllowed(AiProvider $provider, string $model): void
    {
        if (! $provider->enabled) {
            throw new InvalidArgumentException('provider_disabled');
        }
        if ($provider->health !== 'ok') {
            throw new InvalidArgumentException('provider_unhealthy');
        }
        $checked = $provider->models_checked_at;
        if ($checked === null || $checked->lt(now()->subHours(self::DISCOVERY_MAX_AGE_HOURS))) {
            throw new InvalidArgumentException('model_discovery_stale');
        }
        if (! in_array($model, $provider->models_cache ?? [], true)) {
            throw new InvalidArgumentException('model_not_discovered');
        }
        $tier = $this->presets()[$provider->preset]['free_tier'] ?? 'none';
        $allowlist = array_values(array_filter(
            (array) Config::get('ai_providers.free_models.'.$provider->preset, []),
            'is_string',
        ));
        FreePolicy::assertInferenceAllowed($tier, $model, $allowlist);
    }

    /** @return array<string, mixed> */
    public function present(AiProvider $provider): array
    {
        $tier = $this->presets()[$provider->preset]['free_tier'] ?? 'none';

        return [
            'id' => $provider->id,
            'name' => $provider->name,
            'preset' => $provider->preset,
            'host' => (string) parse_url($provider->base_url, PHP_URL_HOST),
            'key_mask' => '••••'.$provider->key_last4,
            'enabled' => $provider->enabled,
            'zero_spend' => true,
            'credit_balance' => 'unknown',
            'free_tier' => $tier,
            'default_model' => $provider->default_model,
            'fallback_models' => $provider->fallback_models ?? [],
            'models' => $provider->models_cache ?? [],
            'health' => $provider->health,
            'health_checked_at' => $provider->health_checked_at?->toIso8601String(),
            'error_code' => $provider->last_error_code,
            'rate_limit' => $provider->rate_limit ?? ['status' => 'unknown'],
        ];
    }
}
