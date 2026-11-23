<?php

declare(strict_types=1);

namespace Tests\Feature\Commerce;

use App\Models\User;
use App\Services\Commerce\OmniDeskOrderPlanBinder;
use App\Services\Commerce\OmniDeskVerifiedPaidFulfillment;
use App\Services\Licensing\OmniDeskLicenseContract;
use App\Services\Payments\OmniDeskVerifiedLiveCapture;
use App\Services\Payments\OmniDeskVerifiedLivePaymentSource;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Facades\DB;
use KMJ\MainPlatform\Catalog\Models\Plan;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Commerce\Models\CommercialOrder;
use KMJ\MainPlatform\Commerce\Services\CommercialOrderService;
use KMJ\MainPlatform\Entitlements\Models\EntitlementPolicy;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;
use Tests\TestCase;

final class OmniDeskVerifiedPaidFulfillmentTest extends TestCase
{
    use RefreshDatabase;

    /** @return array{order:CommercialOrder,actor:User,org:string,plan:Plan,product:Product} */
    private function ready(): array
    {
        config()->set('omnidesk-licensing.paid_plan_binding_enabled', true);
        config()->set('omnidesk-licensing.live_paid_fulfillment_enabled', true);
        config()->set('payment-providers.live_charging_enabled', true);
        $actor = User::factory()->create(['email_verified_at' => now()]);
        $org = app(OrganizationCreator::class)->create('Paid settlement test organization', $actor->id);
        $product = Product::query()->create([
            'slug' => OmniDeskLicenseContract::PRODUCT_SLUG,
            'name' => 'KMJ OmniDesk',
            'status' => 'active',
            'lifecycle' => 'available',
            'is_public' => true,
            'purchase_enabled' => true,
            'licensing_enabled' => true,
        ]);
        $plan = Plan::query()->create([
            'product_id' => $product->getKey(),
            'code' => 'omnidesk.professional',
            'name' => 'OmniDesk Professional',
            'pricing_model' => 'subscription',
            'billing_interval' => 'monthly',
            'currency' => 'INR',
            'amount_minor' => 249900,
            'status' => 'active',
            'trial_days' => 0,
            'features' => [],
            'limits' => [],
        ]);
        EntitlementPolicy::query()->create([
            'product_id' => $product->getKey(),
            'code' => OmniDeskVerifiedPaidFulfillment::POLICY_CODE,
            'capability' => OmniDeskLicenseContract::CAPABILITY,
            'status' => 'active',
        ]);
        $order = app(CommercialOrderService::class)->request(
            (string) $org->getKey(),
            (string) $product->getKey(),
            (int) $actor->getKey(),
            'paid-fulfillment:'.(string) $org->getKey(),
        );
        app(OmniDeskOrderPlanBinder::class)->bind(
            $actor, (string) $order->getKey(), (string) $plan->getKey(),
        );

        // TEST fixture only: these rows are not a real provider receipt.
        // Production still has NO bound LIVE settlement adapter.
        DB::table('commerce_provider_orders')->insert([
            'commercial_order_id' => $order->getKey(),
            'provider' => 'razorpay',
            'provider_order_id' => 'order_TESTCAPTURE',
            'amount_minor' => 249900,
            'currency' => 'INR',
            'environment' => 'live',
            'created_at' => now(),
            'updated_at' => now(),
        ]);
        DB::table('payment_webhook_events')->insert([
            'provider' => 'razorpay',
            'event_id' => 'evt_TESTCAPTURE',
            'event_type' => 'payment.captured',
            'provider_order_id' => 'order_TESTCAPTURE',
            'provider_payment_id' => 'pay_TESTCAPTURE',
            'payload_sha256' => str_repeat('a', 64),
            'processing_status' => 'reconciled',
            'processing_note' => 'CONFIRMED',
            'received_at' => now(),
            'created_at' => now(),
            'updated_at' => now(),
        ]);
        app(CommercialOrderService::class)->confirm(
            (string) $order->getKey(),
            (int) $actor->getKey(),
            'INR',
            249900,
            'razorpay:pay_TESTCAPTURE',
        );

        return [
            'order' => $order, 'actor' => $actor, 'org' => (string) $org->getKey(),
            'plan' => $plan, 'product' => $product,
        ];
    }

    private function fixtureVerifier(
        bool $captured = true,
        int $refundedMinor = 0,
        string $environment = 'live',
        int $amountMinor = 249900,
    ): OmniDeskVerifiedLivePaymentSource {
        return new class($captured, $refundedMinor, $environment, $amountMinor) implements OmniDeskVerifiedLivePaymentSource
        {
            public function __construct(
                private readonly bool $captured,
                private readonly int $refundedMinor,
                private readonly string $environment,
                private readonly int $amountMinor,
            ) {}

            public function verifyCaptured(string $providerOrderId, string $paymentReference): OmniDeskVerifiedLiveCapture
            {
                return new OmniDeskVerifiedLiveCapture(
                    provider: 'razorpay',
                    providerOrderId: $providerOrderId,
                    paymentReference: $paymentReference,
                    environment: $this->environment,
                    currency: 'INR',
                    amountMinor: $this->amountMinor,
                    refundedMinor: $this->refundedMinor,
                    captured: $this->captured,
                );
            }
        };
    }

    public function test_verified_live_fixture_issues_one_bounded_paid_period_and_audits_without_device_signing(): void
    {
        $f = $this->ready();
        $service = app(OmniDeskVerifiedPaidFulfillment::class);
        $first = $service->fulfill((string) $f['order']->getKey(), $this->fixtureVerifier());
        $second = $service->fulfill((string) $f['order']->getKey(), $this->fixtureVerifier());

        self::assertFalse($first['already_exists']);
        self::assertTrue($second['already_exists']);
        self::assertSame($first['license_id'], $second['license_id']);
        self::assertSame($first['entitlement_id'], $second['entitlement_id']);
        $this->assertDatabaseHas('kslp_licenses', [
            'id' => $first['license_id'],
            'customer_id' => $f['org'],
            'product' => OmniDeskLicenseContract::PRODUCT_ID,
            'plan' => 'professional',
            'status' => 'active',
        ]);
        $this->assertDatabaseHas('entitlements', [
            'id' => $first['entitlement_id'],
            'organization_id' => $f['org'],
            'capability' => OmniDeskLicenseContract::CAPABILITY,
        ]);
        $this->assertDatabaseHas('commerce_paid_fulfillments', [
            'commercial_order_id' => $f['order']->getKey(),
            'license_id' => $first['license_id'],
            'entitlement_id' => $first['entitlement_id'],
            'payment_reference' => 'pay_TESTCAPTURE',
        ]);
        $this->assertDatabaseHas('kslp_license_events', [
            'license_id' => $first['license_id'],
            'action' => 'omnidesk_paid_auto_fulfilled',
        ]);
        $this->assertDatabaseHas('commerce_ledger', [
            'order_id' => $f['order']->getKey(),
            'event_type' => 'commerce.order.fulfilled',
        ]);
        $this->assertDatabaseCount('kslp_licenses', 1);
        $this->assertDatabaseCount('entitlements', 1);
        $this->assertDatabaseCount('commerce_paid_fulfillments', 1);
        $this->assertDatabaseCount('kslp_activations', 0);
        $this->assertDatabaseCount('omnidesk_activation_bindings', 0);
        $this->assertDatabaseCount('kslp_license_events', 1);
        $this->assertDatabaseCount('commerce_ledger', 3);
    }

    public function test_disabled_paid_flag_blocks_all_issuance_even_with_fake_test_rows(): void
    {
        $f = $this->ready();
        config()->set('omnidesk-licensing.live_paid_fulfillment_enabled', false);

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('OMNIDESK_PAID_FULFILLMENT_DISABLED');
        app(OmniDeskVerifiedPaidFulfillment::class)
            ->fulfill((string) $f['order']->getKey(), $this->fixtureVerifier());
    }

    public function test_sandbox_evidence_or_refund_cannot_be_promoted_to_paid_license(): void
    {
        $f = $this->ready();
        $service = app(OmniDeskVerifiedPaidFulfillment::class);
        foreach ([
            $this->fixtureVerifier(environment: 'sandbox'),
            $this->fixtureVerifier(refundedMinor: 100),
            $this->fixtureVerifier(captured: false),
            $this->fixtureVerifier(amountMinor: 100),
        ] as $invalid) {
            try {
                $service->fulfill((string) $f['order']->getKey(), $invalid);
                self::fail('Provider capture mismatch must fail closed.');
            } catch (DomainException $exception) {
                self::assertSame('OMNIDESK_PAYMENT_NOT_VERIFIED_LIVE', $exception->getMessage());
            }
        }
        $this->assertDatabaseCount('kslp_licenses', 0);
        $this->assertDatabaseCount('entitlements', 0);
        $this->assertDatabaseCount('commerce_paid_fulfillments', 0);
    }

    public function test_generic_confirmed_order_without_reconciled_signed_event_grants_nothing(): void
    {
        $f = $this->ready();
        DB::table('payment_webhook_events')->update(['processing_status' => 'received']);

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('OMNIDESK_PROVIDER_RECONCILIATION_REQUIRED');
        app(OmniDeskVerifiedPaidFulfillment::class)
            ->fulfill((string) $f['order']->getKey(), $this->fixtureVerifier());
    }

    public function test_wrong_product_price_term_or_paused_policy_blocks_fulfillment(): void
    {
        $f = $this->ready();
        $service = app(OmniDeskVerifiedPaidFulfillment::class);

        $f['plan']->forceFill(['amount_minor' => 999900])->save();
        try {
            $service->fulfill((string) $f['order']->getKey(), $this->fixtureVerifier());
            self::fail('Changed price after checkout must be refused.');
        } catch (DomainException $exception) {
            self::assertSame('OMNIDESK_COMMERCIAL_POLICY_NOT_APPROVED', $exception->getMessage());
        }
        $f['plan']->forceFill(['amount_minor' => 249900])->save();
        EntitlementPolicy::query()
            ->where('code', OmniDeskVerifiedPaidFulfillment::POLICY_CODE)
            ->update(['status' => 'paused']);

        try {
            $service->fulfill((string) $f['order']->getKey(), $this->fixtureVerifier());
            self::fail('Paused entitlement policy must fail closed.');
        } catch (DomainException $exception) {
            self::assertSame('OMNIDESK_PAID_ENTITLEMENT_POLICY_NOT_APPROVED', $exception->getMessage());
        }
        $this->assertDatabaseCount('kslp_licenses', 0);
        $this->assertDatabaseCount('entitlements', 0);
    }

    public function test_existing_organization_license_cannot_be_silently_replaced_by_paid_grant(): void
    {
        $f = $this->ready();
        $now = now();
        DB::table('kslp_licenses')->insert([
            'id' => '22222222-2222-4222-8222-222222222222',
            'customer_id' => $f['org'],
            'product' => OmniDeskLicenseContract::PRODUCT_ID,
            'plan' => 'trial',
            'status' => 'active',
            'sequence' => 1,
            'starts_at' => $now,
            'expires_at' => $now->copy()->addDays(5),
            'created_at' => $now,
            'updated_at' => $now,
        ]);

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('OMNIDESK_EXISTING_LICENSE_CONFLICT');
        app(OmniDeskVerifiedPaidFulfillment::class)
            ->fulfill((string) $f['order']->getKey(), $this->fixtureVerifier());
    }

    public function test_automatic_paid_worker_requires_actual_live_adapter_and_valid_owner_flags(): void
    {
        $f = $this->ready();
        // Even a bogus database event cannot make an unbound LIVE verifier.
        self::assertSame(1, Artisan::call('licensing:fulfill-omnidesk-paid'));
        $this->assertDatabaseCount('kslp_licenses', 0);
        $this->assertDatabaseCount('entitlements', 0);

        config()->set('omnidesk-licensing.live_paid_fulfillment_enabled', false);
        self::assertSame(0, Artisan::call('licensing:fulfill-omnidesk-paid'));
        $this->assertDatabaseCount('commerce_paid_fulfillments', 0);

        // No source path creates real payments or communicates with PSP.
        self::assertSame('confirmed', $f['order']->refresh()->status);
    }

    public function test_approved_mock_adapter_drives_bounded_reconciler_idempotently_in_test_only(): void
    {
        $this->ready();
        app()->bind(
            OmniDeskVerifiedLivePaymentSource::class,
            fn (): OmniDeskVerifiedLivePaymentSource => $this->fixtureVerifier(),
        );

        self::assertSame(0, Artisan::call('licensing:fulfill-omnidesk-paid'));
        $this->assertDatabaseCount('commerce_paid_fulfillments', 1);
        self::assertSame(0, Artisan::call('licensing:fulfill-omnidesk-paid'));
        $this->assertDatabaseCount('commerce_paid_fulfillments', 1);
        $this->assertDatabaseCount('kslp_licenses', 1);
        $this->assertDatabaseCount('kslp_activations', 0);
    }
}
