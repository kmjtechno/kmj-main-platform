<?php

namespace Tests\Unit;

use App\Services\Operations\ProviderCompliancePolicy;
use Tests\TestCase;

final class ProviderCompliancePolicyTest extends TestCase
{
    public function test_unconfigured_policy_fails_closed(): void
    {
        config()->set('kmj.ops.provider_policy', []);

        $snapshot = app(ProviderCompliancePolicy::class)->snapshot();

        self::assertSame('unconfigured', $snapshot['status']);
        self::assertSame('not_enabled', $snapshot['enforcement']);
        self::assertFalse($snapshot['legal_interpretation']);
        self::assertSame([], $snapshot['sources']);
        self::assertSame([], $snapshot['rules']);
    }

    public function test_unapproved_policy_cannot_enable_provider_rules(): void
    {
        config()->set('kmj.ops.provider_policy', $this->profile(approved: false));

        $snapshot = app(ProviderCompliancePolicy::class)->snapshot();

        self::assertSame('pending_review', $snapshot['status']);
        self::assertSame('not_enabled', $snapshot['enforcement']);
    }

    public function test_approved_profile_exposes_only_hash_addressed_sources_and_rules(): void
    {
        config()->set('kmj.ops.provider_policy', $this->profile(approved: true));

        $snapshot = app(ProviderCompliancePolicy::class)->snapshot();

        self::assertSame('active', $snapshot['status']);
        self::assertSame('approved_rules_registered', $snapshot['enforcement']);
        self::assertSame('web-host-example', $snapshot['provider_id']);
        self::assertSame('2026-09-22', $snapshot['policy_version']);
        self::assertCount(1, $snapshot['sources']);
        self::assertCount(1, $snapshot['rules']);
        self::assertSame('resource.cpu.warning', $snapshot['rules'][0]['code']);
        self::assertFalse($snapshot['legal_interpretation']);
    }

    public function test_stale_or_invalid_profile_fails_closed(): void
    {
        $stale = $this->profile(approved: true);
        $stale['reviewed_at'] = now()->subDays(120)->toIso8601String();
        config()->set('kmj.ops.provider_policy', $stale);

        self::assertSame('stale', app(ProviderCompliancePolicy::class)->snapshot()['status']);

        $invalid = $this->profile(approved: true);
        $invalid['sources'][0]['sha256'] = 'not-a-sha256';
        config()->set('kmj.ops.provider_policy', $invalid);

        $snapshot = app(ProviderCompliancePolicy::class)->snapshot();
        self::assertSame('invalid', $snapshot['status']);
        self::assertSame('not_enabled', $snapshot['enforcement']);
    }

    /** @return array<string, mixed> */
    private function profile(bool $approved): array
    {
        return [
            'provider_id' => 'web-host-example',
            'policy_version' => '2026-09-22',
            'approved' => $approved,
            'reviewed_at' => now()->toIso8601String(),
            'max_age_days' => 90,
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
