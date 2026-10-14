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
            $approved = $this->selectableModels($provider);
            if (($default !== null && ! in_array($default, $approved, true))
                || array_diff($fallbacks, $approved) !== []) {
                throw new InvalidArgumentException('zero_spend_model_required');
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

            // Setup is read-only: model discovery makes no inference calls.
            // Preserve an owner's eligible default, but reject stale/paid picks
            // and seed only policy-eligible zero-spend fallback candidates.
            $eligible = $this->selectableModels($provider);
            $current = $provider->default_model;
            $provider->default_model = in_array($current, $eligible, true)
                ? $current : ($eligible[0] ?? null);
            $kept = array_values(array_filter(
                (array) ($provider->fallback_models ?? []),
                fn ($model): bool => in_array($model, $eligible, true)
                    && $model !== $provider->default_model,
            ));
            $provider->fallback_models = array_slice(array_values(array_unique([
                ...$kept,
                ...array_values(array_filter(
                    $eligible,
                    fn (string $model): bool => $model !== $provider->default_model,
                )),
            ])), 0, 5);
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

    /** Only configured provider-verified free IDs are suitable for UI model selection. */
    /** @return list<string> */
    private function selectableModels(AiProvider $provider): array
    {
        $tier = $this->presets()[$provider->preset]['free_tier'] ?? 'none';
        $allowlist = array_values(array_filter(
            (array) Config::get('ai_providers.free_models.'.$provider->preset, []),
            'is_string',
        ));

        return array_values(array_filter(
            (array) ($provider->models_cache ?? []),
            static fn ($model): bool => is_string($model)
                && FreePolicy::inferenceAllowed($tier, $model, $allowlist),
        ));
    }

    /** @return array<string, mixed> */
    public function present(AiProvider $provider): array
    {
        $tier = $this->presets()[$provider->preset]['free_tier'] ?? 'none';
        $freeModels = $this->selectableModels($provider);
        $healthyRecent = $provider->enabled && $provider->health === 'ok'
            && $provider->models_checked_at !== null
            && $provider->models_checked_at->gte(now()->subHours(self::DISCOVERY_MAX_AGE_HOURS));

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
            'default_model' => in_array($provider->default_model, $freeModels, true) ? $provider->default_model : null,
            'fallback_models' => array_values(array_intersect($provider->fallback_models ?? [], $freeModels)),
            'models' => $freeModels,
            'eligible_free_models_count' => count($freeModels),
            'discovered_models_count' => count($provider->models_cache ?? []),
            // Model list/health means provider discovery succeeded; no lease-bound CodeBridge
            // runtime cloud inference integration has been verified by this manager.
            'inference_readiness' => $healthyRecent && $freeModels !== [] ? 'eligible_for_routing' : 'blocked',
            'codebridge_execution' => 'not_verified',
            'health' => $provider->health,
            'health_checked_at' => $provider->health_checked_at?->toIso8601String(),
            'error_code' => $provider->last_error_code,
            'rate_limit' => $provider->rate_limit ?? ['status' => 'unknown'],
        ];
    }
}
