<?php

namespace App\Services\Operations;

use Carbon\CarbonImmutable;
use Throwable;

final class ProviderCompliancePolicy
{
    /** @return array<string, mixed> */
    public function snapshot(): array
    {
        $config = (array) config('kmj.ops.provider_policy', []);
        $providerId = $this->canonicalId($config['provider_id'] ?? null);
        $policyVersion = $this->canonicalText($config['policy_version'] ?? null);

        if ($providerId === null || $policyVersion === null) {
            return $this->result('unconfigured');
        }

        $sources = $this->sources($config['sources'] ?? null);
        if ($sources === null) {
            return $this->result('invalid', $providerId, $policyVersion);
        }

        $rules = $this->rules($config['rules'] ?? null, array_column($sources, 'id'));
        if ($rules === null) {
            return $this->result('invalid', $providerId, $policyVersion);
        }

        if (($config['approved'] ?? false) !== true) {
            return $this->result('pending_review', $providerId, $policyVersion, $sources, $rules);
        }

        $reviewedAt = $this->reviewedAt($config['reviewed_at'] ?? null);
        if ($reviewedAt === null) {
            return $this->result('invalid', $providerId, $policyVersion);
        }

        $maxAgeDays = max(1, (int) ($config['max_age_days'] ?? 90));
        if ($reviewedAt->diffInDays(now()->utc(), true) > $maxAgeDays) {
            return $this->result('stale', $providerId, $policyVersion, $sources, $rules, $reviewedAt);
        }

        return $this->result('active', $providerId, $policyVersion, $sources, $rules, $reviewedAt);
    }

    /**
     * @param  array<int, array<string, mixed>>  $sources
     * @param  array<int, array<string, mixed>>  $rules
     * @return array<string, mixed>
     */
    private function result(
        string $status,
        ?string $providerId = null,
        ?string $policyVersion = null,
        array $sources = [],
        array $rules = [],
        ?CarbonImmutable $reviewedAt = null,
    ): array {
        return [
            'status' => $status,
            'provider_id' => $providerId,
            'policy_version' => $policyVersion,
            'reviewed_at' => $reviewedAt?->toIso8601String(),
            'policy_fingerprint' => $providerId !== null && $policyVersion !== null
                ? $this->fingerprint($providerId, $policyVersion, $sources, $rules)
                : null,
            'enforcement' => $status === 'active' && $rules !== []
                ? 'approved_rules_registered'
                : 'not_enabled',
            'legal_interpretation' => false,
            'sources' => $sources,
            'rules' => $rules,
        ];
    }

    /** @return array<int, array{id: string, url: string, sha256: string}>|null */
    private function sources(mixed $raw): ?array
    {
        if (! is_array($raw)) {
            return [];
        }

        $sources = [];
        $ids = [];

        foreach ($raw as $source) {
            if (! is_array($source)) {
                return null;
            }

            $id = $this->canonicalId($source['id'] ?? null);
            $url = $this->canonicalText($source['url'] ?? null);
            $sha256 = $this->canonicalText($source['sha256'] ?? null);

            if (
                $id === null
                || $url === null
                || filter_var($url, FILTER_VALIDATE_URL) === false
                || ! str_starts_with(strtolower($url), 'https://')
                || $sha256 === null
                || preg_match('/^[0-9a-f]{64}$/', $sha256) !== 1
                || isset($ids[$id])
            ) {
                return null;
            }

            $ids[$id] = true;
            $sources[] = ['id' => $id, 'url' => $url, 'sha256' => $sha256];
        }

        return $sources;
    }

    /**
     * @param  array<int, string>  $sourceIds
     * @return array<int, array<string, mixed>>|null
     */
    private function rules(mixed $raw, array $sourceIds): ?array
    {
        if (! is_array($raw)) {
            return [];
        }

        $allowedMetrics = [
            'cpu.load_percent_estimate',
            'memory.used_percent',
            'disk.used_percent',
            'queue.failed_jobs',
        ];
        $allowedOperators = ['gte', 'gt', 'lte', 'lt', 'eq'];
        $sourceLookup = array_fill_keys($sourceIds, true);
        $rules = [];
        $codes = [];

        foreach ($raw as $rule) {
            if (! is_array($rule)) {
                return null;
            }

            $code = $this->canonicalId($rule['code'] ?? null);
            $sourceId = $this->canonicalId($rule['source_id'] ?? null);
            $metric = $this->canonicalText($rule['metric'] ?? null);
            $operator = $this->canonicalText($rule['operator'] ?? null);
            $value = $rule['value'] ?? null;

            if (
                $code === null
                || $sourceId === null
                || ! isset($sourceLookup[$sourceId])
                || $metric === null
                || ! in_array($metric, $allowedMetrics, true)
                || $operator === null
                || ! in_array($operator, $allowedOperators, true)
                || (! is_int($value) && ! is_float($value))
                || isset($codes[$code])
            ) {
                return null;
            }

            $codes[$code] = true;
            $rules[] = [
                'code' => $code,
                'source_id' => $sourceId,
                'metric' => $metric,
                'operator' => $operator,
                'value' => $value,
            ];
        }

        return $rules;
    }

    /**
     * @param  array<int, array<string, mixed>>  $sources
     * @param  array<int, array<string, mixed>>  $rules
     */
    private function fingerprint(
        string $providerId,
        string $policyVersion,
        array $sources,
        array $rules,
    ): string {
        usort($sources, fn (array $left, array $right): int => ($left['id'] ?? '') <=> ($right['id'] ?? ''));
        usort($rules, fn (array $left, array $right): int => ($left['code'] ?? '') <=> ($right['code'] ?? ''));

        $payload = json_encode([
            'provider_id' => $providerId,
            'policy_version' => $policyVersion,
            'sources' => $sources,
            'rules' => $rules,
        ], JSON_THROW_ON_ERROR);

        return hash('sha256', $payload);
    }

    private function reviewedAt(mixed $value): ?CarbonImmutable
    {
        if (! is_string($value) || trim($value) !== $value || $value === '') {
            return null;
        }

        try {
            return CarbonImmutable::parse($value)->utc();
        } catch (Throwable) {
            return null;
        }
    }

    private function canonicalId(mixed $value): ?string
    {
        if (! is_string($value) || trim($value) !== $value || preg_match('/^[a-z0-9][a-z0-9._-]{1,127}$/', $value) !== 1) {
            return null;
        }

        return $value;
    }

    private function canonicalText(mixed $value): ?string
    {
        return is_string($value) && trim($value) === $value && $value !== '' ? $value : null;
    }
}
