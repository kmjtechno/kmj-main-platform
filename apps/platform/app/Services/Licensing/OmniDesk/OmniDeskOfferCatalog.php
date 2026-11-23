<?php

declare(strict_types=1);

namespace App\Services\Licensing\OmniDesk;

use App\Services\Licensing\OmniDeskLicenseContract;
use DomainException;
use Illuminate\Support\Facades\DB;
use KMJ\MainPlatform\Catalog\Models\Plan;
use KMJ\MainPlatform\Catalog\Models\Product;

/**
 * Owner-directed, competitor-benchmarked INR launch offers — prepared, not
 * published. All new catalog plans are PAUSED: source, a checkout snapshot or
 * a rendered price card never activates a paid or free signed device lease.
 *
 * Billing: transparent plan totals, before any applicable tax, no automatic
 * card charge or recurring mandate until the approved PSP flow is live.
 */
final class OmniDeskOfferCatalog
{
    public const VERSION = '2026-11-23-INR-v1';

    public const TRIAL_DAYS = 14;

    /**
     * Plan codes are globally unique in the existing catalog. Monthly and
     * yearly commitments MUST have separate codes to preserve immutable
     * order-price and term binding.
     *
     * @return array<string, array{name:string,pricing_model:string,billing_interval:?string,currency:?string,amount_minor:?int,trial_days:int,features:array<string,bool>,limits:array<string,int|string>}>
     */
    public static function offers(): array
    {
        $trial = [
            'licensed_users' => 2,
            'managed_devices' => 10,
            'concurrent_sessions' => 1,
            'unattended_devices' => 5,
            'relay_bytes_monthly' => 1073741824,
            'relay_policy' => 'direct_preferred',
        ];

        $free = [
            'licensed_users' => 1,
            'managed_devices' => 1,
            'concurrent_sessions' => 1,
            'unattended_devices' => 0,
            'relay_bytes_monthly' => 0,
            'relay_policy' => 'direct_only',
        ];

        $professional = [
            'licensed_users' => 1,
            'managed_devices' => 3,
            'concurrent_sessions' => 1,
            'unattended_devices' => 2,
            'relay_bytes_monthly' => 2147483648,
            'relay_policy' => 'direct_preferred',
        ];

        $business = [
            'licensed_users' => 5,
            'managed_devices' => 25,
            'concurrent_sessions' => 2,
            'unattended_devices' => 15,
            'relay_bytes_monthly' => 21474836480,
            'relay_policy' => 'direct_preferred',
        ];

        $enterprise = [
            'licensed_users' => 20,
            'managed_devices' => 100,
            'concurrent_sessions' => 5,
            'unattended_devices' => 75,
            'relay_bytes_monthly' => 107374182400,
            'relay_policy' => 'direct_preferred',
        ];

        return [
            'omnidesk.personal_free' => self::offer(
                'Personal Free', 'free', null, null, null, 0,
                ['remote.interactive' => true, 'commercial_use' => false, 'file.transfer' => false],
                $free,
            ),
            'omnidesk.trial' => self::offer(
                '14-Day Business Trial', 'trial', null, null, null, self::TRIAL_DAYS,
                ['remote.interactive' => true, 'commercial_use' => true, 'file.transfer' => true],
                $trial,
            ),
            'omnidesk.professional.monthly' => self::offer(
                'Professional Monthly', 'subscription', 'monthly', 'INR', 14900, 0,
                ['remote.interactive' => true, 'commercial_use' => true, 'file.transfer' => true],
                $professional,
            ),
            'omnidesk.professional.yearly' => self::offer(
                'Professional Yearly', 'subscription', 'yearly', 'INR', 149000, 0,
                ['remote.interactive' => true, 'commercial_use' => true, 'file.transfer' => true],
                $professional,
            ),
            'omnidesk.business.monthly' => self::offer(
                'Business Monthly', 'subscription', 'monthly', 'INR', 49900, 0,
                ['remote.interactive' => true, 'commercial_use' => true, 'file.transfer' => true],
                $business,
            ),
            'omnidesk.business.yearly' => self::offer(
                'Business Yearly', 'subscription', 'yearly', 'INR', 499000, 0,
                ['remote.interactive' => true, 'commercial_use' => true, 'file.transfer' => true],
                $business,
            ),
            'omnidesk.enterprise.monthly' => self::offer(
                'Enterprise Monthly', 'subscription', 'monthly', 'INR', 149900, 0,
                ['remote.interactive' => true, 'commercial_use' => true, 'file.transfer' => true],
                $enterprise,
            ),
            'omnidesk.enterprise.yearly' => self::offer(
                'Enterprise Yearly', 'subscription', 'yearly', 'INR', 1499000, 0,
                ['remote.interactive' => true, 'commercial_use' => true, 'file.transfer' => true],
                $enterprise,
            ),
            'omnidesk.custom_oem' => self::offer(
                'Custom / OEM (Quote Only)', 'quote', null, null, null, 0,
                ['remote.interactive' => false, 'commercial_use' => false, 'file.transfer' => false],
                $free,
            ),
        ];
    }

    /**
     * @param  array<string, bool>  $features
     * @param  array<string, int|string>  $limits
     * @return array{name:string,pricing_model:string,billing_interval:?string,currency:?string,amount_minor:?int,trial_days:int,features:array<string,bool>,limits:array<string,int|string>}
     */
    private static function offer(
        string $name,
        string $pricingModel,
        ?string $interval,
        ?string $currency,
        ?int $amountMinor,
        int $days,
        array $features,
        array $limits,
    ): array {
        return [
            'name' => $name,
            'pricing_model' => $pricingModel,
            'billing_interval' => $interval,
            'currency' => $currency,
            'amount_minor' => $amountMinor,
            'trial_days' => $days,
            'features' => $features,
            'limits' => $limits,
        ];
    }

    /**
     * PREPARE ONLY. Never changes product state, purchase flags, plan status,
     * entitlement policy, trial/free issuance, PSP settings or signer.
     *
     * @return array{created:int,unchanged:int,product_id:string}
     */
    public function prepare(): array
    {
        return DB::transaction(function (): array {
            $product = Product::query()
                ->where('slug', OmniDeskLicenseContract::PRODUCT_SLUG)
                ->lockForUpdate()
                ->first();
            if (! $product instanceof Product) {
                throw new DomainException('OMNIDESK_CATALOG_PRODUCT_MISSING');
            }

            $created = $unchanged = 0;
            foreach (self::offers() as $code => $facts) {
                $existing = Plan::query()->where('code', $code)->lockForUpdate()->first();
                if ($existing instanceof Plan) {
                    if ((string) $existing->getAttribute('product_id') !== (string) $product->getKey()) {
                        throw new DomainException('OMNIDESK_CATALOG_CROSS_PRODUCT_CODE_CONFLICT');
                    }
                    foreach ($facts as $key => $value) {
                        if ($existing->getAttribute($key) !== $value) {
                            throw new DomainException('OMNIDESK_CATALOG_PRICE_OR_POLICY_CONFLICT');
                        }
                    }
                    $unchanged++;

                    continue;
                }

                Plan::query()->create([
                    'product_id' => (string) $product->getKey(),
                    'code' => $code,
                    ...$facts,
                    'status' => 'paused',
                ]);
                $created++;
            }

            return [
                'created' => $created,
                'unchanged' => $unchanged,
                'product_id' => (string) $product->getKey(),
            ];
        }, 3);
    }

    /** @return list<array{code:string,name:string,amount_minor:?int,currency:?string,billing_interval:?string,trial_days:int,licensed_users:int,managed_devices:int,concurrent_sessions:int,available:bool}> */
    public function preview(): array
    {
        $product = Product::query()->where('slug', OmniDeskLicenseContract::PRODUCT_SLUG)->first();
        $activeProduct = $product instanceof Product
            && $product->getAttribute('status') === 'active'
            && $product->getAttribute('licensing_enabled') === true
            && $product->getAttribute('purchase_enabled') === true
            && in_array($product->getAttribute('lifecycle'), ['available', 'public-beta'], true);

        $plans = Plan::query()->whereIn('code', array_keys(self::offers()))
            ->get()->keyBy('code');

        $result = [];
        foreach (self::offers() as $code => $offer) {
            $plan = $plans->get($code);
            $limits = $offer['limits'];
            $result[] = [
                'code' => $code,
                'name' => $offer['name'],
                'amount_minor' => $offer['amount_minor'],
                'currency' => $offer['currency'],
                'billing_interval' => $offer['billing_interval'],
                'trial_days' => $offer['trial_days'],
                'licensed_users' => (int) $limits['licensed_users'],
                'managed_devices' => (int) $limits['managed_devices'],
                'concurrent_sessions' => (int) $limits['concurrent_sessions'],
                'available' => $activeProduct
                    && $plan instanceof Plan
                    && $plan->getAttribute('status') === 'active'
                    && $plan->getAttribute('product_id') === $product?->getKey(),
            ];
        }

        return $result;
    }
}
