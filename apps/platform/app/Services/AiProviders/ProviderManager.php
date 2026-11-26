<?php

declare(strict_types=1);

namespace App\Services\AiProviders;

use App\Models\AiModelEvidence;
use App\Models\AiModelRule;
use App\Models\AiProvider;
use Illuminate\Support\Facades\Config;
use Illuminate\Support\Facades\DB;
use InvalidArgumentException;
use RuntimeException;

final class ProviderManager
{
    private const DISCOVERY_MAX_AGE_HOURS = 24;

    public function __construct(
        private readonly OpenAiCompatibleAdapter $adapter,
        private readonly EndpointGuard $guard,
    ) {}

    /** @return array<string, array{label: string, base_url: ?string, free_tier: string, retired?: bool}> */
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
        if ($preset['retired'] ?? false) {
            throw new InvalidArgumentException('provider_retired');
        }
        $baseUrl = $preset['base_url'] ?? ($data['base_url'] ?? null);
        if (! is_string($baseUrl) || $baseUrl === '') {
            throw new InvalidArgumentException('endpoint_scheme');
        }
        $this->guard->validate($baseUrl, $this->approvedHosts());
        $apiKey = (string) ($data['api_key'] ?? '');
        if ($presetKey === 'kilo-free' && $apiKey !== '') {
            throw new InvalidArgumentException('keyless_provider');
        }

        return AiProvider::query()->create([
            'organization_id' => $organizationId,
            'name' => (string) ($data['name'] ?? ''),
            'preset' => $presetKey,
            'kind' => 'openai-compatible',
            'base_url' => $baseUrl,
            'api_key' => $apiKey,
            'key_last4' => substr($apiKey, -4),
            'free_only' => true,
            // Persist and hydrate the existing enabled-by-default policy immediately.
            // A newly created model does not hydrate database defaults until refresh.
            'enabled' => true,
            'created_by' => $userId,
        ]);
    }

    /** @param array<string, mixed> $data */
    public function update(AiProvider $provider, array $data): AiProvider
    {
        $replacingKey = isset($data['api_key']) && is_string($data['api_key']) && $data['api_key'] !== '';
        if ($replacingKey) {
            if ($provider->preset === 'kilo-free') {
                throw new InvalidArgumentException('keyless_provider');
            }
            if ($this->presets()[$provider->preset]['retired'] ?? false) {
                throw new InvalidArgumentException('provider_retired');
            }
            $provider->api_key = $data['api_key'];
            $provider->key_last4 = substr($data['api_key'], -4);
            // A replaced key invalidates earlier health and model evidence.
            $provider->health = 'unknown';
            $provider->health_checked_at = null;
            $provider->last_error_code = null;
            $provider->rate_limit = null;
            $provider->models_cache = null;
            $provider->models_checked_at = null;
            $provider->default_model = null;
            $provider->fallback_models = [];
        }
        foreach (['name', 'enabled'] as $field) {
            if (array_key_exists($field, $data)) {
                $provider->{$field} = $data[$field];
            }
        }
        if (array_key_exists('default_model', $data) || array_key_exists('fallback_models', $data)) {
            // A discovered model is not necessarily free. Never persist an unadmitted
            // paid/unknown-price default or fallback just because GET /models listed it.
            $known = $this->admittedFreeModels($provider);
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
        DB::transaction(function () use ($provider, $replacingKey): void {
            $provider->save();
            if ($replacingKey) {
                // A replacement may belong to a different billing account. Preserve
                // historical evidence, but require fresh owner attestation before reuse.
                $now = now();
                AiModelRule::query()->where('ai_provider_id', $provider->id)
                    ->where('organization_id', $provider->organization_id)
                    ->whereNull('revoked_at')->where('expires_at', '>', $now)
                    ->update(['expires_at' => $now]);
                AiModelEvidence::query()->where('ai_provider_id', $provider->id)
                    ->where('organization_id', $provider->organization_id)
                    ->whereNull('revoked_at')->where('expires_at', '>', $now)
                    ->update(['expires_at' => $now]);
            }
        });

        return $provider;
    }

    public function test(AiProvider $provider): AiProvider
    {
        if ($this->presets()[$provider->preset]['retired'] ?? false) {
            $provider->health = 'blocked';
            $provider->health_checked_at = now();
            $provider->last_error_code = 'provider_retired';
            $provider->models_cache = null;
            $provider->models_checked_at = null;
            $provider->rate_limit = ['status' => 'unknown'];
            $provider->save();

            return $provider;
        }

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
     * Only currently usable free models may appear as selectable defaults/fallbacks.
     * A successful catalog probe is not billing evidence for an arbitrary model.
     *
     * @return list<string>
     */
    public function admittedFreeModels(AiProvider $provider): array
    {
        if (! $provider->enabled || $provider->health !== 'ok'
            || $provider->models_checked_at === null
            || $provider->models_checked_at->lt(now()->subHours(self::DISCOVERY_MAX_AGE_HOURS))) {
            return [];
        }

        if ($provider->preset === 'kilo-free' && ($provider->api_key !== ''
            || $provider->base_url !== ($this->presets()['kilo-free']['base_url'] ?? null))) {
            return [];
        }
        $tier = $this->presets()[$provider->preset]['free_tier'] ?? 'none';
        $allowlist = $tier === 'catalog-free' && $provider->preset === 'kilo-free'
            ? array_values($provider->models_cache ?? []) : $this->allowlist($provider, $tier);

        return array_values(array_filter(
            $provider->models_cache ?? [],
            fn (string $model): bool => ($provider->preset !== 'kilo-free' || OpenAiCompatibleAdapter::kiloPublicModel($model))
                && FreePolicy::inferenceAllowed($tier, $model, $allowlist),
        ));
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
        if ($this->presets()[$provider->preset]['retired'] ?? false) {
            throw new InvalidArgumentException('provider_retired');
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
        if ($provider->preset === 'kilo-free' && ($provider->api_key !== ''
            || $provider->base_url !== ($this->presets()['kilo-free']['base_url'] ?? null)
            || ! OpenAiCompatibleAdapter::kiloPublicModel($model))) {
            throw new InvalidArgumentException('zero_spend_blocked');
        }
        $tier = $this->presets()[$provider->preset]['free_tier'] ?? 'none';
        $allowlist = $tier === 'catalog-free' && $provider->preset === 'kilo-free'
            ? array_values($provider->models_cache ?? []) : $this->allowlist($provider, $tier);
        FreePolicy::assertInferenceAllowed($tier, $model, $allowlist);
    }

    /**
     * Server-env verified-free ids plus owner price evidence that is still current. Evidence only
     * counts on the allowlist tier: it can never unlock a provider with no free tier, and it
     * expires on its own, so a stale claim stops admitting inference without any cleanup job.
     *
     * @return list<string>
     */
    private function allowlist(AiProvider $provider, string $tier): array
    {
        $ids = array_values(array_filter(
            (array) Config::get('ai_providers.free_models.'.$provider->preset, []),
            'is_string',
        ));
        if ($tier !== 'allowlist') {
            return $ids;
        }

        $evidence = AiModelEvidence::query()
            ->where('ai_provider_id', $provider->id)
            ->where('organization_id', $provider->organization_id)
            ->get(['model_id', 'revoked_at', 'expires_at']);
        // Explicit per-connection evidence wins over a global environment default,
        // including revoked or expired evidence. Do not silently restore that route.
        $ids = array_diff($ids, $evidence->pluck('model_id')->all());
        $current = $evidence->filter(fn (AiModelEvidence $row): bool => $row->isCurrent())->pluck('model_id')->all();

        return array_values(array_unique([...$ids, ...array_filter($current, 'is_string')]));
    }

    /**
     * Sends one chat completion, but only after the zero-spend admission guard passes.
     * There is no paid or fallback route: a refusal is returned as an error code.
     *
     * @param  list<array{role: string, content: string}>  $messages
     * @return array{ok: bool, content: ?string, error_code: ?string, rate?: array{requests_remaining: ?int, tokens_remaining: ?int, retry_after: ?int, daily_requests_limit?: int, daily_reset_seconds?: int}}
     */
    public function complete(AiProvider $provider, string $model, array $messages, ?int $strictCodingTokens = null): array
    {
        try {
            $this->assertInferenceAllowed($provider, $model);
        } catch (InvalidArgumentException|RuntimeException $exception) {
            return ['ok' => false, 'content' => null, 'error_code' => $exception->getMessage()];
        }

        return $this->adapter->complete($provider->base_url, $provider->api_key, $this->approvedHosts(), $model, $messages, $strictCodingTokens);
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
            'key_mask' => $provider->preset === 'kilo-free' ? 'Not required' : '••••'.$provider->key_last4,
            'enabled' => $provider->enabled,
            'zero_spend' => true,
            'credit_balance' => 'unknown',
            'free_tier' => $tier,
            'default_model' => $provider->default_model,
            'fallback_models' => $provider->fallback_models ?? [],
            'models' => $this->admittedFreeModels($provider),
            'discovered_model_count' => count($provider->models_cache ?? []),
            'health' => $provider->health,
            'health_checked_at' => $provider->health_checked_at?->toIso8601String(),
            'error_code' => ($this->presets()[$provider->preset]['retired'] ?? false) ? 'provider_retired' : $provider->last_error_code,
            'rate_limit' => $provider->rate_limit ?? ['status' => 'unknown'],
        ];
    }
}
