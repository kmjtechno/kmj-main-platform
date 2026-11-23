<?php

declare(strict_types=1);

namespace Tests\Feature\Commerce;

use App\Models\User;
use App\Services\Commerce\OmniDeskOrderPlanBinder;
use App\Services\Licensing\OmniDeskLicenseContract;
use App\Services\Payments\RazorpayCheckoutOrders;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Route;
use KMJ\MainPlatform\Catalog\Models\Plan;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Commerce\Models\CommercialOrder;
use KMJ\MainPlatform\Commerce\Services\CommercialOrderService;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;
use Tests\TestCase;

final class OmniDeskPaidPlanSnapshotTest extends TestCase
{
    use RefreshDatabase;

    /** @return array{actor:User,order:CommercialOrder,plan:Plan,product:Product,org:string} */
    private function ready(): array
    {
        config()->set('omnidesk-licensing.paid_plan_binding_enabled', true);

        $actor = User::factory()->create(['email_verified_at' => now()]);
        $org = app(OrganizationCreator::class)->create('Paid checkout lab', $actor->id);
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
        $order = app(CommercialOrderService::class)->request(
            (string) $org->getKey(),
            (string) $product->getKey(),
            (int) $actor->getKey(),
            'paid-plan-test-'.(string) $org->getKey(),
        );

        return [
            'actor' => $actor, 'order' => $order, 'plan' => $plan,
            'product' => $product, 'org' => (string) $org->getKey(),
        ];
    }

    public function test_verified_customer_binds_immutable_server_price_and_term_without_paid_grant(): void
    {
        $f = $this->ready();
        $binder = app(OmniDeskOrderPlanBinder::class);
        $first = $binder->bind($f['actor'], (string) $f['order']->getKey(), (string) $f['plan']->getKey());
        $second = $binder->bind($f['actor'], (string) $f['order']->getKey(), (string) $f['plan']->getKey());
        self::assertSame($first, $second);
        self::assertSame('INR', $first['currency']);
        self::assertSame(249900, $first['amount_minor']);
        self::assertSame('monthly', $first['billing_interval']);
        $this->assertDatabaseHas('commerce_order_plan_snapshots', [
            'commercial_order_id' => (string) $f['order']->getKey(),
            'organization_id' => $f['org'],
            'plan_id' => (string) $f['plan']->getKey(),
            'currency' => 'INR',
            'amount_minor' => 249900,
        ]);
        $this->assertDatabaseCount('commerce_order_plan_snapshots', 1);
        $this->assertDatabaseCount('entitlements', 0);
        $this->assertDatabaseCount('kslp_licenses', 0);
        $this->assertDatabaseCount('commerce_provider_orders', 0);
    }

    public function test_disabled_flag_unverified_user_or_cross_tenant_checkout_cannot_bind(): void
    {
        $f = $this->ready();
        $binder = app(OmniDeskOrderPlanBinder::class);
        config()->set('omnidesk-licensing.paid_plan_binding_enabled', false);

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('OMNIDESK_PLAN_BINDING_DISABLED');
        $binder->bind($f['actor'], (string) $f['order']->getKey(), (string) $f['plan']->getKey());
    }

    public function test_paid_plan_http_is_protected_and_does_not_mutate_foreign_orders(): void
    {
        $f = $this->ready();
        $name = 'purchase.orders.omnidesk.plan';
        $route = Route::getRoutes()->getByName($name);
        self::assertNotNull($route);
        self::assertContains('web', $route->gatherMiddleware());
        self::assertContains('auth', $route->gatherMiddleware());
        self::assertContains('verified', $route->gatherMiddleware());
        $path = '/purchase/orders/'.$f['order']->getKey().'/omnidesk-plan';
        $this->post($path, ['plan_id' => $f['plan']->getKey()])
            ->assertRedirect('/login');

        $outsider = User::factory()->create(['email_verified_at' => now()]);
        $this->actingAs($outsider)->post($path, ['plan_id' => $f['plan']->getKey()])
            ->assertForbidden();
        $this->assertDatabaseCount('commerce_order_plan_snapshots', 0);

        $this->actingAs($f['actor'])->post($path, ['plan_id' => $f['plan']->getKey()])
            ->assertRedirect(route('purchase.index'));
        $this->assertDatabaseCount('commerce_order_plan_snapshots', 1);
        $this->assertDatabaseCount('entitlements', 0);
    }

    public function test_unapproved_or_changed_plan_never_overwrites_original_price(): void
    {
        $f = $this->ready();
        $binder = app(OmniDeskOrderPlanBinder::class);
        $binder->bind($f['actor'], (string) $f['order']->getKey(), (string) $f['plan']->getKey());

        $f['plan']->forceFill(['amount_minor' => 799900])->save();
        try {
            $binder->bind($f['actor'], (string) $f['order']->getKey(), (string) $f['plan']->getKey());
            self::fail('A changed catalog price must not rewrite buyer consent.');
        } catch (DomainException $exception) {
            self::assertSame('OMNIDESK_PLAN_BINDING_CONFLICT', $exception->getMessage());
        }
        $this->assertDatabaseHas('commerce_order_plan_snapshots', [
            'commercial_order_id' => $f['order']->getKey(),
            'amount_minor' => 249900,
        ]);

        $f['plan']->forceFill(['status' => 'paused'])->save();
        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('OMNIDESK_PLAN_NOT_APPROVED');
        $binder->bind($f['actor'], (string) $f['order']->getKey(), (string) $f['plan']->getKey());
    }

    public function test_unapproved_product_or_wrong_plan_price_fails_closed(): void
    {
        $f = $this->ready();
        $binder = app(OmniDeskOrderPlanBinder::class);
        $f['product']->forceFill(['lifecycle' => 'research'])->save();
        try {
            $binder->bind($f['actor'], (string) $f['order']->getKey(), (string) $f['plan']->getKey());
            self::fail('Research products must not allow paid plan checkout.');
        } catch (DomainException $e) {
            self::assertSame('OMNIDESK_PLAN_NOT_APPROVED', $e->getMessage());
        }

        $f['product']->forceFill(['lifecycle' => 'available'])->save();
        $f['plan']->forceFill(['currency' => 'USD'])->save();
        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('OMNIDESK_PLAN_NOT_APPROVED');
        $binder->bind($f['actor'], (string) $f['order']->getKey(), (string) $f['plan']->getKey());
    }

    public function test_provider_order_never_opens_from_an_omnidesk_amount_without_snapshot(): void
    {
        $f = $this->ready();
        Http::fake();

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('OMNIDESK_CHECKOUT_PLAN_OR_PRICE_MISMATCH');
        app(RazorpayCheckoutOrders::class)->open((string) $f['order']->getKey(), 249900);
    }

    public function test_provider_order_wrong_amount_fails_even_with_valid_plan_snapshot(): void
    {
        $f = $this->ready();
        app(OmniDeskOrderPlanBinder::class)->bind(
            $f['actor'], (string) $f['order']->getKey(), (string) $f['plan']->getKey(),
        );
        Http::fake();

        try {
            app(RazorpayCheckoutOrders::class)->open((string) $f['order']->getKey(), 349900);
            self::fail('A caller must not replace the immutable plan amount.');
        } catch (DomainException $e) {
            self::assertSame('OMNIDESK_CHECKOUT_PLAN_OR_PRICE_MISMATCH', $e->getMessage());
        }
        Http::assertNothingSent();
        $this->assertDatabaseCount('commerce_provider_orders', 0);
        $this->assertDatabaseCount('kslp_licenses', 0);
    }

    public function test_owner_plan_preference_does_not_override_checkout_after_provider_binding(): void
    {
        $f = $this->ready();
        DB::table('commerce_provider_orders')->insert([
            'commercial_order_id' => $f['order']->getKey(),
            'provider' => 'razorpay',
            'provider_order_id' => 'order_PREBOUND',
            'amount_minor' => 249900,
            'currency' => 'INR',
            'environment' => 'sandbox',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('OMNIDESK_CHECKOUT_ALREADY_OPEN');
        app(OmniDeskOrderPlanBinder::class)->bind(
            $f['actor'], (string) $f['order']->getKey(), (string) $f['plan']->getKey(),
        );
    }
}
