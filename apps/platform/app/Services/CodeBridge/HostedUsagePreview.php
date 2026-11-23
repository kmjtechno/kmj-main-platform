<?php

declare(strict_types=1);

namespace App\Services\CodeBridge;

/**
 * Public-facing, source-only plan comparison.
 *
 * THIS IS NOT a usage meter. Do not read or infer counts from the unwired
 * codebridge_usage_periods table, a client parameter or a KSLP license tier.
 * Until an authenticated seat resolver + real gateway execution receipts are
 * deployed, there is no trustworthy customer usage number to display.
 */
final class HostedUsagePreview
{
    /** @return array<string, mixed> */
    public function catalog(): array
    {
        return [
            'status' => 'proposal_only',
            'meter_live' => false,
            'checkout_live' => false,
            'trial_live' => false,
            'used_calls' => null,
            'remaining_calls' => null,
            'next_reset_at' => null,
            'active_plan' => null,
            'unit' => 'completed_remote_tool_calls',
            'period' => 'calendar_month_utc',
            'self_hosted_unmetered' => true,
            'ai_provider_fees_included' => false,
            'plans' => [
                ['id' => 'community', 'label' => 'Community', 'monthly_calls' => 10000, 'monthly_price_inr' => 0, 'per_user' => false],
                ['id' => 'pro', 'label' => 'Pro', 'monthly_calls' => 100000, 'monthly_price_inr' => 299, 'per_user' => false],
                ['id' => 'team', 'label' => 'Team', 'monthly_calls' => 300000, 'monthly_price_inr' => 699, 'per_user' => true],
                ['id' => 'business', 'label' => 'Business', 'monthly_calls' => null, 'monthly_price_inr' => null, 'per_user' => false],
            ],
        ];
    }
}
