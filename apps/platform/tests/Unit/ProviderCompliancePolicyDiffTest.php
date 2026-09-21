<?php

namespace Tests\Unit;

use App\Services\Operations\ProviderCompliancePolicyDiff;
use Tests\TestCase;

final class ProviderCompliancePolicyDiffTest extends TestCase
{
    public function test_identical_approved_snapshots_are_unchanged(): void
    {
        $snapshot = $this->snapshot();

        $diff = app(ProviderCompliancePolicyDiff::class)->compare($snapshot, $snapshot);

        self::assertSame('unchanged', $diff['status']);
        self::assertFalse($diff['review_required']);
        self::assertSame([], $diff['changes']);
    }

    public function test_source_hash_and_rule_value_changes_require_review(): void
    {
        $previous = $this->snapshot();
        $current = $this->snapshot();
        $current['sources'][0]['sha256'] = str_repeat('b', 64);
        $current['rules'][0]['value'] = 85;

        $diff = app(ProviderCompliancePolicyDiff::class)->compare($previous, $current);

        self::assertSame('changed', $diff['status']);
        self::assertTrue($diff['review_required']);
        self::assertContains('source:resource-policy', $diff['changes']);
        self::assertContains('rule:resource.cpu.warning', $diff['changes']);
    }

    public function test_provider_or_policy_version_change_requires_review(): void
    {
        $previous = $this->snapshot();
        $current = $this->snapshot();
        $current['policy_version'] = '2026-10-01';

        $diff = app(ProviderCompliancePolicyDiff::class)->compare($previous, $current);

        self::assertSame('changed', $diff['status']);
        self::assertTrue($diff['review_required']);
        self::assertContains('policy_version', $diff['changes']);
        self::assertFalse($diff['legal_interpretation']);
    }

    /** @return array<string, mixed> */
    private function snapshot(): array
    {
        return [
            'status' => 'active',
            'provider_id' => 'web-host-example',
            'policy_version' => '2026-09-22',
            'sources' => [[
                'id' => 'resource-policy',
                'url' => 'https://provider.example/policy',
                'sha256' => str_repeat('a', 64),
            ]],
            'rules' => [[
                'code' => 'resource.cpu.warning',
                'source_id' => 'resource-policy',
                'metric' => 'cpu.load_percent_estimate',
                'operator' => 'gte',
                'value' => 80,
            ]],
        ];
    }
}
