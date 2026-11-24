<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use App\Services\AuthorityBootstrapper;
use App\Services\Licensing\Kslp\KslpCommercialOrderTerms;
use App\Services\Licensing\Kslp\KslpIssuerSubscriptionAuthority;
use App\Services\Payments\RazorpayCheckoutOrders;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Str;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Commerce\Services\CommercialOrderService;
use Tests\TestCase;

final class KslpCommercialOrderTermsTest extends TestCase
{
    use RefreshDatabase;

    private function owner(): User
    {
        $owner = User::factory()->create([
            'email_verified_at' => now(),
            'is_platform_owner' => true,
            'platform_owner_granted_at' => now(),
        ]);
        DB::table('passkeys')->insert([
            'user_id' => $owner->id,
            'name' => 'Order terms owner',
            'credential_id' => 'order-terms-'.Str::uuid(),
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $owner;
    }

    /** @return array{string, string, string, string} */
    private function scope(User $actor, string $suffix): array
    {
        $organization = app(AuthorityBootstrapper::class)
            ->createOrganizationWithSandboxAccess('Order terms '.$suffix, $actor->id);
        $org = (string) $organization->getKey();
        $issuer = app(KslpIssuerSubscriptionAuthority::class);
        $issuer->subscribe($org, 'professional', 3, 10);
        $product = $issuer->registerProduct($org, 'TERMS.'.$suffix, 'Terms app '.$suffix);
        $catalog = Product::query()->create([
            'slug' => 'terms-'.strtolower($suffix),
            'name' => 'Terms purchase '.$suffix,
            'status' => 'preview',
        ]);
        $catalogId = (string) $catalog->getKey();
        $order = app(CommercialOrderService::class)->request(
            $org, $catalogId, $actor->id, 'terms-order-'.$suffix
        );

        return [$org, (string) $product['id'], (string) $order->getKey(), $catalogId];
    }

    public function test_exact_terms_match_is_not_payment_settlement_or_paid_issuance(): void
    {
        $owner = $this->owner();
        $actor = User::factory()->create(['email_verified_at' => now()]);
        [$org, $product, $order, $catalog] = $this->scope($actor, 'ALPHA');
        $terms = app(KslpCommercialOrderTerms::class);
        self::assertSame('binding_missing', $terms->inspect($actor->id, $org, $product, $order)['status']);

        $terms->record($owner, $org, $product, $order, $catalog, 'INR', 25000, 'Review exact order terms');
        self::assertSame('order_not_confirmed', $terms->inspect($actor->id, $org, $product, $order)['status']);
        $this->assertDatabaseHas('license_audit_events', [
            'organization_id' => $org,
            'actor_id' => $owner->id,
            'action' => 'kslp_commercial_order_terms_recorded',
        ]);

        app(CommercialOrderService::class)->confirm($order, $actor->id, 'INR', 25000, 'manual-confirmation');
        $result = $terms->inspect($actor->id, $org, $product, $order);
        self::assertSame('terms_match_not_settled', $result['status']);
        self::assertTrue($result['terms_match']);
        self::assertFalse($result['verified_live_settlement']);
        self::assertFalse($result['paid_issuance_enabled']);

        $another = app(KslpIssuerSubscriptionAuthority::class)
            ->registerProduct($org, 'TERMS.OTHER', 'Other application');
        self::assertFalse($terms->inspect($actor->id, $org, (string) $another['id'], $order)['terms_match']);

        DB::table('commerce_orders')->where('id', $order)->update(['amount_minor' => 24999]);
        self::assertSame('amount_or_currency_mismatch', $terms->inspect($actor->id, $org, $product, $order)['status']);
        DB::table('commerce_orders')->where('id', $order)->update(['amount_minor' => 25000, 'currency' => 'USD']);
        self::assertFalse($terms->inspect($actor->id, $org, $product, $order)['terms_match']);
        DB::table('commerce_orders')->where('id', $order)->update(['currency' => 'INR']);
        DB::table('products')->where('id', $catalog)->update(['slug' => 'changed-terms-alpha']);
        self::assertSame('binding_mismatch', $terms->inspect($actor->id, $org, $product, $order)['status']);
        $this->assertDatabaseCount('kslp_commercial_order_terms', 1);
        $this->assertDatabaseCount('kslp_licenses', 0);
        $this->assertDatabaseCount('kslp_reseller_credit_ledger', 0);
    }

    public function test_wrong_catalog_and_foreign_product_are_rejected_before_recording(): void
    {
        $owner = $this->owner();
        $actor = User::factory()->create(['email_verified_at' => now()]);
        $other = User::factory()->create(['email_verified_at' => now()]);
        [$org, $product, $order, $catalog] = $this->scope($actor, 'BETA');
        [, $foreignProduct, , $foreignCatalog] = $this->scope($other, 'GAMMA');
        $terms = app(KslpCommercialOrderTerms::class);
        foreach ([[$product, $foreignCatalog], [$foreignProduct, $catalog]] as [$candidate, $sku]) {
            try {
                $terms->record($owner, $org, $candidate, $order, $sku, 'INR', 25000, 'Reject mismatched binding');
                self::fail('Foreign or mismatched product scope must be rejected.');
            } catch (DomainException $exception) {
                self::assertSame('KSLP_ORDER_TERMS_SCOPE_INVALID', $exception->getMessage());
            }
        }

        $this->assertDatabaseCount('kslp_commercial_order_terms', 0);
        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('KSLP_ORDER_TERMS_ACCESS_DENIED');
        $terms->inspect($other->id, $org, $product, $order);
    }

    public function test_reviewed_checkout_requires_exact_binding_before_any_provider_call(): void
    {
        $owner = $this->owner();
        $actor = User::factory()->create(['email_verified_at' => now()]);
        [$org, $product, $order, $catalog] = $this->scope($actor, 'CHECKOUT');
        $terms = app(KslpCommercialOrderTerms::class);
        $checkout = app(RazorpayCheckoutOrders::class);
        Http::fake([
            'api.razorpay.com/v1/orders' => fn (Request $request) => Http::response([
                'id' => 'order_TERMS1',
                'receipt' => $request['receipt'],
                'currency' => 'INR',
                'amount' => $request['amount'],
                'status' => 'created',
                'amount_paid' => 0,
                'amount_due' => $request['amount'],
            ]),
        ]);

        try {
            $checkout->openReviewed($order, $product, 25000);
            self::fail('Missing reviewed terms must deny checkout.');
        } catch (DomainException $exception) {
            self::assertSame('RAZORPAY_REVIEWED_TERMS_REQUIRED', $exception->getMessage());
        }

        $terms->record($owner, $org, $product, $order, $catalog, 'INR', 25000, 'Review sandbox checkout terms');
        foreach ([
            fn () => $checkout->openReviewed($order, 'wrong-product', 25000),
            fn () => $checkout->openReviewed($order, $product, 24999),
            fn () => $checkout->open($order, 24999),
        ] as $attempt) {
            try {
                $attempt();
                self::fail('Mismatched terms must fail before provider access.');
            } catch (DomainException $exception) {
                self::assertSame('RAZORPAY_REVIEWED_TERMS_MISMATCH', $exception->getMessage());
            }
        }
        Http::assertNothingSent();
        $this->assertDatabaseCount('commerce_provider_order_intents', 0);

        DB::table('payment_gateway_settings')->insert([
            'provider' => 'razorpay',
            'environment' => 'sandbox',
            'merchant_status' => 'not_verified',
            'international_requested' => false,
            'encrypted_client_id' => Crypt::encryptString('rzp_test_ABC123'),
            'encrypted_client_secret' => Crypt::encryptString('sandbox-secret-value'),
            'created_at' => now(),
            'updated_at' => now(),
        ]);
        $created = $checkout->openReviewed($order, $product, 25000);
        self::assertSame('order_TERMS1', $created['provider_order_id']);
        self::assertSame($created, $checkout->openReviewed($order, $product, 25000));
        Http::assertSentCount(1);
        $this->assertDatabaseHas('commerce_orders', ['id' => $order, 'status' => 'requested']);
        $this->assertDatabaseHas('commerce_provider_orders', [
            'commercial_order_id' => $order, 'environment' => 'sandbox',
        ]);
        $this->assertDatabaseCount('kslp_licenses', 0);
        $this->assertDatabaseCount('kslp_reseller_credit_ledger', 0);
    }

    public function test_product_drift_during_provider_http_preserves_intent_and_blocks_link(): void
    {
        $owner = $this->owner();
        $actor = User::factory()->create(['email_verified_at' => now()]);
        [$org, $product, $order, $catalog] = $this->scope($actor, 'DRIFT');
        app(KslpCommercialOrderTerms::class)->record(
            $owner, $org, $product, $order, $catalog, 'INR', 25000, 'Review exact sandbox order terms'
        );

        DB::table('payment_gateway_settings')->insert([
            'provider' => 'razorpay',
            'environment' => 'sandbox',
            'merchant_status' => 'not_verified',
            'international_requested' => false,
            'encrypted_client_id' => Crypt::encryptString('rzp_test_ABC123'),
            'encrypted_client_secret' => Crypt::encryptString('sandbox-secret-value'),
            'created_at' => now(),
            'updated_at' => now(),
        ]);
        $transactionDepth = DB::transactionLevel();
        Http::fake([
            'api.razorpay.com/v1/orders' => function (Request $request) use ($catalog, $transactionDepth) {
                self::assertSame($transactionDepth, DB::transactionLevel());
                DB::table('products')->where('id', $catalog)->update(['slug' => 'changed-during-http']);

                return Http::response([
                    'id' => 'order_DRIFT1',
                    'receipt' => $request['receipt'],
                    'currency' => 'INR',
                    'amount' => $request['amount'],
                    'status' => 'created',
                    'amount_paid' => 0,
                    'amount_due' => $request['amount'],
                ]);
            },
        ]);
        $checkout = app(RazorpayCheckoutOrders::class);
        try {
            $checkout->openReviewed($order, $product, 25000);
            self::fail('Changed catalog identity must not be linked to the provider response.');
        } catch (DomainException $exception) {
            self::assertSame('RAZORPAY_REVIEWED_TERMS_MISMATCH', $exception->getMessage());
        }

        $this->assertDatabaseHas('commerce_provider_order_intents', [
            'commercial_order_id' => $order,
            'creation_status' => 'creating',
        ]);
        $this->assertDatabaseMissing('commerce_provider_orders', ['commercial_order_id' => $order]);
        DB::table('products')->where('id', $catalog)->update(['slug' => 'terms-drift']);

        try {
            $checkout->openReviewed($order, $product, 25000);
            self::fail('Restored terms must not cause duplicate provider creation.');
        } catch (DomainException $exception) {
            self::assertSame('RAZORPAY_ORDER_CREATION_PENDING_REVIEW', $exception->getMessage());
        }
        Http::assertSentCount(1);
        $this->assertDatabaseCount('kslp_licenses', 0);
        $this->assertDatabaseCount('kslp_reseller_credit_ledger', 0);
    }

    public function test_existing_unresolved_provider_intent_prevents_retroactive_terms(): void
    {
        $owner = $this->owner();
        $actor = User::factory()->create(['email_verified_at' => now()]);
        [$org, $product, $order, $catalog] = $this->scope($actor, 'INTENT');
        DB::table('commerce_provider_order_intents')->insert([
            'commercial_order_id' => $order,
            'provider' => 'razorpay',
            'amount_minor' => 25000,
            'currency' => 'INR',
            'creation_status' => 'creating',
            'created_at' => now(),
            'updated_at' => now(),
        ]);
        try {
            app(KslpCommercialOrderTerms::class)->record(
                $owner, $org, $product, $order, $catalog, 'INR', 25000, 'Attempt retroactive order terms'
            );
            self::fail('Uncertain provider creation must prevent retroactive terms.');
        } catch (DomainException $exception) {
            self::assertSame('KSLP_ORDER_TERMS_ORDER_ALREADY_PROCESSED', $exception->getMessage());
        }
        $this->assertDatabaseCount('kslp_commercial_order_terms', 0);
        $this->assertDatabaseCount('commerce_provider_orders', 0);
    }

    public function test_terms_cannot_be_overwritten_or_retrofitted_after_confirmation(): void
    {
        $owner = $this->owner();
        $actor = User::factory()->create(['email_verified_at' => now()]);
        [$org, $product, $order, $catalog] = $this->scope($actor, 'DELTA');
        $terms = app(KslpCommercialOrderTerms::class);
        $terms->record($owner, $org, $product, $order, $catalog, 'INR', 25000, 'Original reviewed terms');
        try {
            $terms->record($owner, $org, $product, $order, $catalog, 'INR', 100, 'Attempt changed terms');
            self::fail('Existing terms cannot be replaced.');
        } catch (DomainException $exception) {
            self::assertSame('KSLP_ORDER_TERMS_ALREADY_RECORDED', $exception->getMessage());
        }
        [$otherOrg, $otherProduct, $otherOrder, $otherCatalog] = $this->scope($actor, 'EPSILON');
        app(CommercialOrderService::class)->confirm($otherOrder, $actor->id, 'INR', 25000, 'already-confirmed');
        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('KSLP_ORDER_TERMS_ORDER_ALREADY_PROCESSED');
        $terms->record($owner, $otherOrg, $otherProduct, $otherOrder, $otherCatalog, 'INR', 25000, 'Attempt retrospective terms');
    }
}
