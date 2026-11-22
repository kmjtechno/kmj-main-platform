<?php

declare(strict_types=1);

namespace App\Services\AiProviders;

use App\Models\AiModelEvidence;
use App\Models\AiModelRule;
use App\Models\AiProvider;
use App\Models\OperatorActionAudit;

/**
 * Turns active owner rules into ordinary evidence rows for models the provider itself listed.
 * A rule can never approve a revoked model, a non-chat model, more than MAX_MATCHES models, or
 * anything past its own expiry (at most 30 days), and a provider without an owner-verified free
 * allowlist tier is never touched.
 */
final class ModelFabricRuleApplier
{
    public const MAX_MATCHES = 50;

    public const MIN_LITERAL_PREFIX = 10;

    /** Model ids containing any of these are never chat models and are never auto-approved. */
    private const NON_CHAT = ['tts', 'image', 'imagen', 'live', 'audio', 'embedding', 'robotics', 'computer-use', 'translate', 'veo', 'lyria', 'whisper', 'guard', 'safeguard', 'moderation', 'transcribe'];

    public function __construct(private readonly ProviderManager $manager) {}

    /** Returns an error message for an unsafe pattern, or null when it is acceptable. */
    public static function patternError(string $pattern): ?string
    {
        if (preg_match('/\A[A-Za-z0-9._\/*-]{1,96}\z/', $pattern) !== 1) {
            return 'Use only letters, digits . _ / - and * in the pattern.';
        }
        if (substr_count($pattern, '*') > 2 || ! str_contains($pattern, '*')) {
            return 'Use one or two * wildcards, for example models/gemini-2.5-flash*.';
        }
        $prefix = strstr($pattern, '*', true);
        if (! is_string($prefix) || strlen($prefix) < self::MIN_LITERAL_PREFIX) {
            return 'The text before the first * must be at least '.self::MIN_LITERAL_PREFIX.' characters, so a rule cannot approve everything.';
        }

        return null;
    }

    /**
     * @param  array<int, string>  $models
     * @return list<string>
     */
    public static function matches(string $pattern, array $models): array
    {
        $regex = '/\A'.str_replace('\*', '[A-Za-z0-9._\/-]*', preg_quote($pattern, '/')).'\z/';
        $out = [];
        foreach ($models as $model) {
            if (preg_match($regex, $model) !== 1) {
                continue;
            }
            $lower = strtolower($model);
            foreach (self::NON_CHAT as $word) {
                if (str_contains($lower, $word)) {
                    continue 2;
                }
            }
            $out[] = $model;
        }

        return $out;
    }

    /** @return array{rules: int, approved: int, skipped_too_broad: int} */
    public function apply(?AiProvider $only = null): array
    {
        $summary = ['rules' => 0, 'approved' => 0, 'skipped_too_broad' => 0];
        $query = AiModelRule::query()->whereNull('revoked_at')->where('expires_at', '>', now());
        if ($only instanceof AiProvider) {
            $query->where('ai_provider_id', $only->id);
        }
        $rules = $query->get();

        foreach ($rules as $rule) {
            $provider = $rule->provider;
            if (! $provider instanceof AiProvider || ! $provider->enabled || $provider->health !== 'ok') {
                continue;
            }
            if (($this->manager->presets()[$provider->preset]['free_tier'] ?? 'none') !== 'allowlist') {
                continue;
            }
            $summary['rules']++;
            $matched = self::matches($rule->model_pattern, $provider->models_cache ?? []);
            if (count($matched) > self::MAX_MATCHES) {
                $summary['skipped_too_broad']++;

                continue;
            }
            $changed = 0;
            foreach ($matched as $modelId) {
                $existing = AiModelEvidence::query()->where('ai_provider_id', $provider->id)->where('model_id', $modelId)->first();
                if ($existing instanceof AiModelEvidence) {
                    if ($existing->revoked_at !== null) {
                        continue; // an explicit revoke always wins over a rule
                    }
                    if ($existing->ai_model_rule_id === null && $existing->isCurrent()) {
                        continue; // a current manual approval stands
                    }
                    if ($existing->ai_model_rule_id === $rule->id && $existing->expires_at->equalTo($rule->expires_at)) {
                        continue;
                    }
                }
                AiModelEvidence::query()->updateOrCreate(
                    ['ai_provider_id' => $provider->id, 'model_id' => $modelId],
                    [
                        'organization_id' => $rule->organization_id,
                        'ai_model_rule_id' => $rule->id,
                        'price_evidence_url' => $rule->price_evidence_url,
                        'price_evidence_note' => $rule->price_evidence_note,
                        'verified_at' => $rule->attested_at,
                        'expires_at' => $rule->expires_at,
                        'data_handling' => $rule->data_handling,
                        'capabilities' => $rule->capabilities ?? ['chat'],
                        'verified_by' => $rule->attested_by,
                        'cost_class' => 'free',
                        'credit_daily_cap' => null,
                        'credit_hard_cap_attested_at' => null,
                        'revoked_at' => null,
                    ],
                );
                $changed++;
            }
            if ($changed > 0) {
                $summary['approved'] += $changed;
                OperatorActionAudit::query()->create([
                    'actor_user_id' => $rule->attested_by,
                    'action' => 'model_fabric.rule_applied',
                    'outcome' => 'saved',
                    'metadata' => ['provider' => $provider->name, 'pattern' => $rule->model_pattern, 'models' => $changed, 'paid_inference_enabled' => false],
                ]);
            }
        }

        return $summary;
    }
}
