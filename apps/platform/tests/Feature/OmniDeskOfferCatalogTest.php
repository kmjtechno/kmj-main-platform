<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use App\Services\Commerce\KmjProductCatalog;
use App\Services\Licensing\OmniDesk\OmniDeskOfferCatalog;
use App\Services\Licensing\OmniDeskLicenseContract;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Inertia\Testing\AssertableInertia as Assert;
use KMJ\MainPlatform\Catalog\Models\Plan;
use KMJ\MainPlatform\Catalog\Models\Product;
use Tests\TestCase;

final class OmniDeskOfferCatalogTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
    }

    public function test_prepared_catalog_contains_nine_exact_offers_with_annual_two_month_discount(): void
    {
        $product = app(KmjProductCatalog::class)->syncAll()[KmjProductCatalog::OMNIDESK_SLUG];
        $catalog = app(OmniDeskOfferCatalog::class);

        $first = $catalog->prepare();
        self::assertSame(9, $first['created']);
        self::assertSame(0, $first['unchanged']);
        self::assertSame((string) $product->getKey(), $first['product_id']);

        $offers = OmniDeskOfferCatalog::offers();
        self::assertCount(9, $offers);
        self::assertSame(14, $offers['omnidesk.trial']['trial_days']);
        self::assertNull($offers['omnidesk.trial']['amount_minor']);
        self::assertNull($offers['omnidesk.personal_free']['amount_minor']);
        self::assertFalse($offers['omnidesk.personal_free']['features']['commercial_use']);
        self::assertSame('direct_only', $offers['omnidesk.personal_free']['limits']['relay_policy']);

        foreach (['professional' => 14900, 'business' => 49900, 'enterprise' => 149900] as $tier => $monthlyMinor) {
            $monthly = $offers['omnidesk.'.$tier.'.monthly'];
            $yearly = $offers['omnidesk.'.$tier.'.yearly'];
            self::assertSame($monthlyMinor, $monthly['amount_minor']);
            self::assertSame($monthlyMinor * 10, $yearly['amount_minor']);
            self::assertSame('monthly', $monthly['billing_interval']);
            self::assertSame('yearly', $yearly['billing_interval']);
            self::assertSame('INR', $monthly['currency']);
            self::assertSame('INR', $yearly['currency']);
            self::assertSame($monthly['limits'], $yearly['limits']);
        }

        $prepared = $catalog->preview();
        self::assertCount(9, $prepared);
        foreach ($prepared as $offer) {
            self::assertFalse($offer['available']);
            self::assertGreaterThanOrEqual(0, $offer['managed_devices']);
            self::assertGreaterThanOrEqual(0, $offer['unattended_devices']);
        }

        $this->assertDatabaseCount('commerce_orders', 0);
        $this->assertDatabaseCount('entitlements', 0);
        $this->assertDatabaseCount('kslp_licenses', 0);
        $this->assertDatabaseCount('commerce_paid_fulfillments', 0);
        $this->assertDatabaseCount('payment_gateway_settings', 0);
        $this->assertDatabaseHas('products', [
            'id' => $product->getKey(),
            'slug' => OmniDeskLicenseContract::PRODUCT_SLUG,
            'status' => 'sandbox',
            'purchase_enabled' => false,
        ]);
        foreach (array_keys($offers) as $code) {
            $this->assertDatabaseHas('plans', [
                'product_id' => $product->getKey(),
                'code' => $code,
                'status' => 'paused',
            ]);
        }
    }

    public function test_catalog_prepare_replay_is_idempotent_and_never_auto_publishes(): void
    {
        app(KmjProductCatalog::class)->syncAll();
        $catalog = app(OmniDeskOfferCatalog::class);
        self::assertSame(9, $catalog->prepare()['created']);
        self::assertSame(0, $catalog->prepare()['created']);
        self::assertSame(9, $catalog->prepare()['unchanged']);
        self::assertSame(9, Plan::query()->where('product_id', Product::query()->where('slug', OmniDeskLicenseContract::PRODUCT_SLUG)->value('id'))->count());
        $this->assertDatabaseHas('products', [
            'slug' => OmniDeskLicenseContract::PRODUCT_SLUG,
            'status' => 'sandbox',
        ]);
        $this->assertDatabaseCount('kslp_activations', 0);
    }

    public function test_invalid_existing_price_or_plan_ownership_rolls_back_all_new_offers(): void
    {
        $products = app(KmjProductCatalog::class)->syncAll();
        $other = $products[KmjProductCatalog::CLOUDOS_SLUG];
        Plan::query()->create([
            'product_id' => $other->getKey(),
            'code' => 'omnidesk.trial',
            'name' => 'Unknown third-party trial',
            'pricing_model' => 'trial',
            'billing_interval' => null,
            'currency' => null,
            'amount_minor' => null,
            'status' => 'paused',
            'trial_days' => 14,
            'features' => [],
            'limits' => [],
        ]);
        try {
            app(OmniDeskOfferCatalog::class)->prepare();
            self::fail('Foreign plan code ownership must never silently overwrite product pricing.');
        } catch (DomainException $exception) {
            self::assertSame('OMNIDESK_CATALOG_CROSS_PRODUCT_CODE_CONFLICT', $exception->getMessage());
        }

        $omni = $products[KmjProductCatalog::OMNIDESK_SLUG];
        self::assertSame(0, Plan::query()->where('product_id', $omni->getKey())->count());
        $this->assertDatabaseCount('kslp_licenses', 0);
    }

    public function test_price_edit_conflict_never_rewrites_existing_customer_offer(): void
    {
        app(KmjProductCatalog::class)->syncAll();
        $catalog = app(OmniDeskOfferCatalog::class);
        $catalog->prepare();
        Plan::query()->where('code', 'omnidesk.professional.monthly')
            ->update(['amount_minor' => 19900]);

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('OMNIDESK_CATALOG_PRICE_OR_POLICY_CONFLICT');
        $catalog->prepare();
    }

    public function test_regular_account_cannot_prepare_owner_only_paused_pricing(): void
    {
        app(KmjProductCatalog::class)->syncAll();
        $path = '/operator/kslp/omnidesk/offers/prepare';

        $this->post($path)->assertRedirect('/login');
        $regular = User::factory()->create(['email_verified_at' => now()]);
        $this->actingAs($regular)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post($path)->assertForbidden();
        $this->assertDatabaseMissing('plans', ['code' => 'omnidesk.professional.monthly']);
    }

    public function test_verified_passkey_owner_can_prepare_paused_plans_in_one_kslp_hub(): void
    {
        app(KmjProductCatalog::class)->syncAll();
        $owner = User::factory()->create([
            'email_verified_at' => now(),
            'is_platform_owner' => true,
            'platform_owner_granted_at' => now(),
        ]);
        DB::table('passkeys')->insert([
            'user_id' => $owner->getKey(),
            'name' => 'Owner passkey',
            'credential_id' => 'omnidesk-offers-'.Str::uuid(),
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/kslp/omnidesk/offers/prepare')
            ->assertRedirect('/operator/kslp#omnidesk-offers');

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/kslp')->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('operator-kslp')
                ->has('omnideskOffers', 9)
                ->where('omnideskOfferVersion', OmniDeskOfferCatalog::VERSION)
                ->where('omnideskReleaseFlags.trial', false)
                ->where('omnideskReleaseFlags.paid', false)
                ->where('omnideskReleaseFlags.gateway', false));

        $this->assertDatabaseCount('commerce_orders', 0);
        $this->assertDatabaseCount('entitlements', 0);
        $this->assertDatabaseCount('kslp_licenses', 0);
    }

    public function test_customer_purchase_preview_discloses_terms_without_offering_unverified_payment(): void
    {
        app(KmjProductCatalog::class)->syncAll();
        app(OmniDeskOfferCatalog::class)->prepare();
        $customer = User::factory()->create(['email_verified_at' => now()]);

        $this->actingAs($customer)->get('/purchase')->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('purchase')
                ->has('omnideskOffers', 9)
                ->where('omnideskTrialEnabled', false)
                ->where('omnideskPaidCheckoutEnabled', false)
                ->where('omnideskOffers.0.code', 'omnidesk.personal_free')
                ->where('omnideskOffers.0.available', false));
    }
}
