<?php

declare(strict_types=1);

namespace App\Services\AiProviders;

use App\Models\AiModelEvidence;
use App\Models\AiProvider;

/**
 * Verified-zero route planner (ADR-004, roadmap section 15). It never contacts a provider and has
 * no paid or unknown-cost fallback: when nothing qualifies the answer is NO_FREE_ROUTE_AVAILABLE
 * with a per-provider reason, so deterministic build/test/git work continues without an AI route.
 */
final class ModelFabricRouter
{
    public const NO_ROUTE = 'NO_FREE_ROUTE_AVAILABLE';

    public function __construct(private readonly ProviderManager $manager) {}

    /**
     * With $privateSource true a route needs current owner evidence that the provider documents no
     * training on submitted data; unknown data handling never qualifies for private source code.
     *
     * @return array{status: string, routes: list<array<string, mixed>>, reasons: list<array{provider: string, reason: string}>}
     */
    public function plan(string $organizationId, string $capability = 'chat', bool $privateSource = false, bool $strictFreeCloud = false): array
    {
        $routes = [];
        $reasons = [];

        $providers = AiProvider::query()->where('organization_id', $organizationId)->orderBy('name')->get();
        foreach ($providers as $provider) {
            if ($provider->preset === 'kilo-free' && ($privateSource || $strictFreeCloud || $capability !== 'chat')) {
                $reasons[] = ['provider' => $provider->name, 'reason' => 'public_chat_only'];

                continue;
            }
            $evidence = $this->currentEvidence($provider);
            $models = $this->manager->admittedFreeModels($provider);
            if ($models === []) {
                $reasons[] = ['provider' => $provider->name, 'reason' => $this->blockedReason($provider)];

                continue;
            }

            $admitted = 0;
            foreach ($models as $model) {
                $proof = $evidence[$model] ?? null;
                $handling = $proof instanceof AiModelEvidence ? $proof->data_handling : 'unknown';
                $capabilities = $proof instanceof AiModelEvidence ? ($proof->capabilities ?? []) : [];
                if ($privateSource && ($proof === null || $handling !== 'no-training-documented')) {
                    continue;
                }
                if ($capability !== 'chat' && ! in_array($capability, $capabilities, true)) {
                    continue;
                }
                // Strict coding admission excludes credit-limited and custom/local endpoints.
                // This is pricing policy evidence, not an account billing attestation.
                if ($strictFreeCloud && ($proof === null || $proof->cost_class !== 'free'
                    || ($this->manager->presets()[$provider->preset]['base_url'] ?? null) !== $provider->base_url)) {
                    continue;
                }
                $admitted++;
                $routes[] = [
                    'provider_id' => $provider->id,
                    'provider' => $provider->name,
                    'model' => $model,
                    'source' => $proof === null ? 'server-allowlist-or-free-suffix' : 'owner-price-evidence',
                    'evidence_expires_at' => $proof instanceof AiModelEvidence ? $proof->expires_at->toIso8601String() : null,
                    'data_handling' => $handling,
                    // ADR-004 rev 2: credit-limited routes carry the owner-set daily cap the gateway enforces.
                    'cost_class' => $proof instanceof AiModelEvidence ? $proof->cost_class : 'free',
                    'credit_daily_cap' => $proof instanceof AiModelEvidence ? $proof->credit_daily_cap : null,
                ];
            }
            if ($admitted === 0) {
                $reasons[] = ['provider' => $provider->name, 'reason' => $privateSource ? 'no_private_source_evidence' : 'no_capable_model'];
            }
        }

        if ($routes === []) {
            return ['status' => self::NO_ROUTE, 'routes' => [], 'reasons' => $reasons];
        }

        return ['status' => 'ROUTE_AVAILABLE', 'routes' => $routes, 'reasons' => $reasons];
    }

    /** @return array<string, AiModelEvidence> keyed by model id, current (unexpired, unrevoked) only */
    private function currentEvidence(AiProvider $provider): array
    {
        $byModel = [];
        foreach (AiModelEvidence::query()->where('ai_provider_id', $provider->id)->get() as $row) {
            if ($row->isCurrent()) {
                $byModel[$row->model_id] = $row;
            }
        }

        return $byModel;
    }

    private function blockedReason(AiProvider $provider): string
    {
        if (! $provider->enabled) {
            return 'provider_disabled';
        }
        if ($provider->health !== 'ok') {
            return 'provider_unhealthy_run_test_connection';
        }
        if ($provider->models_checked_at === null || $provider->models_checked_at->lt(now()->subHours(24))) {
            return 'model_discovery_stale';
        }

        return 'no_verified_free_model';
    }
}
