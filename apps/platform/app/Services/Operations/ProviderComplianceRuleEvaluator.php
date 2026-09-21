<?php

namespace App\Services\Operations;

final class ProviderComplianceRuleEvaluator
{
    /**
     * @param  array<string, mixed>  $policy
     * @param  array<string, mixed>  $telemetry
     * @return array{
     *     status: 'not_enabled'|'clear'|'breach'|'unobserved'|'invalid',
     *     legal_interpretation: false,
     *     mitigation_allowed: false,
     *     signals: array<int, array<string, mixed>>
     * }
     */
    public function evaluate(array $policy, array $telemetry): array
    {
        if (
            ($policy['status'] ?? null) !== 'active'
            || ($policy['enforcement'] ?? null) !== 'approved_rules_registered'
        ) {
            return $this->result('not_enabled');
        }

        $rules = $policy['rules'] ?? null;
        if (! is_array($rules)) {
            return $this->result('invalid');
        }

        $signals = [];
        $hasBreach = false;
        $hasUnobserved = false;

        foreach ($rules as $rule) {
            if (! is_array($rule)) {
                return $this->result('invalid');
            }

            $code = $rule['code'] ?? null;
            $sourceId = $rule['source_id'] ?? null;
            $metric = $rule['metric'] ?? null;
            $operator = $rule['operator'] ?? null;
            $threshold = $rule['value'] ?? null;

            if (
                ! is_string($code)
                || ! is_string($sourceId)
                || ! is_string($metric)
                || ! is_string($operator)
                || (! is_int($threshold) && ! is_float($threshold))
            ) {
                return $this->result('invalid');
            }

            $observed = $this->metric($telemetry, $metric);

            if ($observed === null) {
                $hasUnobserved = true;
                $signals[] = [
                    'code' => $code,
                    'source_id' => $sourceId,
                    'metric' => $metric,
                    'operator' => $operator,
                    'threshold' => $threshold,
                    'observed' => null,
                    'state' => 'unobserved',
                ];

                continue;
            }

            $breached = $this->compare($observed, $operator, $threshold);
            if ($breached === null) {
                return $this->result('invalid');
            }

            $hasBreach = $hasBreach || $breached;
            $signals[] = [
                'code' => $code,
                'source_id' => $sourceId,
                'metric' => $metric,
                'operator' => $operator,
                'threshold' => $threshold,
                'observed' => $observed,
                'state' => $breached ? 'breach' : 'clear',
            ];
        }

        $status = $hasBreach
            ? 'breach'
            : ($hasUnobserved ? 'unobserved' : 'clear');

        return $this->result($status, $signals);
    }

    /**
     * @param  array<int, array<string, mixed>>  $signals
     * @return array{
     *     status: 'not_enabled'|'clear'|'breach'|'unobserved'|'invalid',
     *     legal_interpretation: false,
     *     mitigation_allowed: false,
     *     signals: array<int, array<string, mixed>>
     * }
     */
    private function result(string $status, array $signals = []): array
    {
        return [
            'status' => $status,
            'legal_interpretation' => false,
            'mitigation_allowed' => false,
            'signals' => $signals,
        ];
    }

    /** @param array<string, mixed> $telemetry */
    private function metric(array $telemetry, string $metric): int|float|null
    {
        $value = match ($metric) {
            'cpu.load_percent_estimate' => data_get($telemetry, 'cpu.load_percent_estimate'),
            'memory.used_percent' => data_get($telemetry, 'memory.used_percent'),
            'disk.used_percent' => data_get($telemetry, 'disk.used_percent'),
            'queue.failed_jobs' => $telemetry['failed_jobs'] ?? null,
            default => null,
        };

        return is_int($value) || is_float($value) ? $value : null;
    }

    private function compare(int|float $observed, string $operator, int|float $threshold): ?bool
    {
        return match ($operator) {
            'gte' => $observed >= $threshold,
            'gt' => $observed > $threshold,
            'lte' => $observed <= $threshold,
            'lt' => $observed < $threshold,
            'eq' => $observed === $threshold,
            default => null,
        };
    }
}
