<?php

namespace Tests\Unit;

use App\Services\Operations\ProviderComplianceRuleEvaluator;
use Tests\TestCase;

final class ProviderComplianceRuleEvaluatorTest extends TestCase
{
    public function test_unapproved_policy_never_evaluates_provider_rules(): void
    {
        $result = app(ProviderComplianceRuleEvaluator::class)->evaluate(
            ['status' => 'pending_review', 'enforcement' => 'not_enabled', 'rules' => []],
            $this->telemetry(),
        );

        self::assertSame('not_enabled', $result['status']);
        self::assertSame([], $result['signals']);
        self::assertFalse($result['mitigation_allowed']);
    }

    public function test_approved_cpu_threshold_breach_is_reported_without_mitigation(): void
    {
        $result = app(ProviderComplianceRuleEvaluator::class)->evaluate(
            $this->activePolicy(),
            $this->telemetry(cpu: 85),
        );

        self::assertSame('breach', $result['status']);
        self::assertCount(1, $result['signals']);
        self::assertSame('resource.cpu.warning', $result['signals'][0]['code']);
        self::assertSame('breach', $result['signals'][0]['state']);
        self::assertSame(85, $result['signals'][0]['observed']);
        self::assertSame(80, $result['signals'][0]['threshold']);
        self::assertFalse($result['mitigation_allowed']);
        self::assertFalse($result['legal_interpretation']);
    }

    public function test_approved_rule_is_clear_when_metric_is_below_threshold(): void
    {
        $result = app(ProviderComplianceRuleEvaluator::class)->evaluate(
            $this->activePolicy(),
            $this->telemetry(cpu: 40),
        );

        self::assertSame('clear', $result['status']);
        self::assertSame('clear', $result['signals'][0]['state']);
    }

    public function test_missing_telemetry_is_explicitly_unobserved(): void
    {
        $telemetry = $this->telemetry();
        unset($telemetry['cpu']);

        $result = app(ProviderComplianceRuleEvaluator::class)->evaluate(
            $this->activePolicy(),
            $telemetry,
        );

        self::assertSame('unobserved', $result['status']);
        self::assertSame('unobserved', $result['signals'][0]['state']);
    }

    /** @return array<string, mixed> */
    private function activePolicy(): array
    {
        return [
            'status' => 'active',
            'enforcement' => 'approved_rules_registered',
            'rules' => [[
                'code' => 'resource.cpu.warning',
                'source_id' => 'resource-policy',
                'metric' => 'cpu.load_percent_estimate',
                'operator' => 'gte',
                'value' => 80,
            ]],
        ];
    }

    /** @return array<string, mixed> */
    private function telemetry(int|float $cpu = 20): array
    {
        return [
            'cpu' => ['load_percent_estimate' => $cpu],
            'memory' => ['used_percent' => 30],
            'disk' => ['used_percent' => 40],
            'failed_jobs' => 0,
        ];
    }
}
