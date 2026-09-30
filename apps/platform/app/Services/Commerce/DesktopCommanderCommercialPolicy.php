<?php

namespace App\Services\Commerce;

final class DesktopCommanderCommercialPolicy
{
    public const PRODUCT_SLUG = KmjProductCatalog::DESKTOP_COMMANDER_SLUG;

    /**
     * Public-beta and future commercial limits are deliberately expressed as
     * entitlements. Project commands never need to transit the KMJ platform.
     *
     * @return array<string, array<string, mixed>>
     */
    public function plans(): array
    {
        return [
            'free' => [
                'label' => 'Free',
                'price_enabled' => false,
                'server_profiles' => 3,
                'devices' => 1,
                'manual_operations' => 'unlimited',
                'autopilot_runs_per_month' => 50,
                'execution_location' => 'customer',
            ],
            'pro' => [
                'label' => 'Pro',
                'price_enabled' => false,
                'server_profiles' => 25,
                'devices' => 3,
                'manual_operations' => 'unlimited',
                'autopilot_runs_per_month' => 2000,
                'execution_location' => 'customer',
            ],
            'team' => [
                'label' => 'Team',
                'price_enabled' => false,
                'server_profiles' => 100,
                'devices' => 10,
                'manual_operations' => 'unlimited',
                'autopilot_runs_per_month' => 10000,
                'execution_location' => 'customer',
            ],
        ];
    }

    /**
     * @return array<string, mixed>
     */
    public function publicBootstrap(): array
    {
        return [
            'schema' => 1,
            'product' => self::PRODUCT_SLUG,
            'channel' => 'public-beta',
            'default_plan' => 'free',
            'billing_enabled' => false,
            'execution_model' => 'local-first',
            'license_authority' => 'kmj-main-platform',
            'entitlement_protocol' => 'KSLP-v1',
            'entitlement_verification' => 'offline-ed25519',
            'entitlement_refresh_seconds' => 604800,
            'bootstrap_refresh_seconds' => 86400,
            'bootstrap_refresh_jitter_seconds' => 21600,
            'idle_license_heartbeat' => false,
            'plans' => $this->plans(),
            'platform_support' => [
                'windows' => 'full',
                'linux' => 'full',
                'macos' => 'full',
                'android' => 'companion',
                'ios' => 'companion',
            ],
        ];
    }
}
