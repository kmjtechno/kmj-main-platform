<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use App\Services\AuthorityBootstrapper;
use App\Services\Licensing\Kslp\KslpCommercialOrderTerms;
use App\Services\Licensing\Kslp\KslpIssuerSubscriptionAuthority;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
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
