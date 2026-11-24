<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use App\Services\Licensing\Kslp\KslpIssuerSubscriptionAuthority;
use App\Services\Licensing\Kslp\KslpResellerCreditEvidenceLedger;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Inertia\Testing\AssertableInertia as Assert;
use KMJ\MainPlatform\Catalog\Models\Product;
use KMJ\MainPlatform\Commerce\Services\CommercialOrderService;
use KMJ\MainPlatform\Organizations\Models\OrganizationMembership;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;
use Tests\TestCase;

final class KslpProductEvidenceWorkspaceTest extends TestCase
{
    use RefreshDatabase;

    /** @return array{string, string, string} */
    private function issuer(User $owner, string $suffix): array
    {
        $org = (string) app(OrganizationCreator::class)->create('Evidence issuer '.$suffix, $owner->id)->getKey();
        $issuer = app(KslpIssuerSubscriptionAuthority::class);
        $issuer->subscribe($org, 'professional', 3, 10);
        $app = $issuer->registerProduct($org, 'EVIDENCE.'.$suffix, 'Evidence app '.$suffix);
        $catalog = Product::query()->create([
            'slug' => 'evidence-workspace-'.strtolower($suffix),
            'name' => 'Evidence order '.$suffix,
            'status' => 'preview',
        ]);
        $order = app(CommercialOrderService::class)->request(
            $org, (string) $catalog->getKey(), $owner->id, 'workspace-evidence-'.$suffix
        );

        return [$org, (string) $app['id'], (string) $order->getKey()];
    }

    public function test_authorized_workspace_shows_only_exact_product_evidence_without_financial_or_secret_fields(): void
    {
        $this->withoutVite();
        $owner = User::factory()->create(['email_verified_at' => now()]);
        $foreignOwner = User::factory()->create(['email_verified_at' => now()]);
        [$org, $product, $order] = $this->issuer($owner, 'ALPHA');
        [$foreignOrg, $foreignProduct, $foreignOrder] = $this->issuer($foreignOwner, 'BETA');
        $emptyProduct = app(KslpIssuerSubscriptionAuthority::class)
            ->registerProduct($org, 'EVIDENCE.EMPTY', 'Empty app');

        $ledger = app(KslpResellerCreditEvidenceLedger::class);
        $ledger->queuePending($owner->id, $org, $product, $order, 'pending:alpha:workspace');
        $ledger->queuePending($foreignOwner->id, $foreignOrg, $foreignProduct, $foreignOrder, 'pending:beta:workspace');
        // Corrupt/mismatched legacy metadata must never be counted even when
        // both referenced IDs individually exist.
        DB::table('kslp_reseller_credit_ledger')->insert([
            'issuer_organization_id' => $foreignOrg,
            'licensed_product_id' => $product,
            'commercial_order_id' => $foreignOrder,
            'event_key_hash' => hash('sha256', 'foreign-product-mismatch'),
            'event_type' => 'evidence_pending',
            'credits_delta' => 0,
            'evidence_state' => 'unverified',
            'actor_user_id' => $foreignOwner->id,
            'created_at' => now(),
        ]);

        $this->actingAs($owner)->get('/developer/apps')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('developer-apps')
                ->has('applications', 2)
                ->where('applications', function ($applications) use ($product, $emptyProduct, $foreignProduct): bool {
                    $byId = collect($applications)->keyBy('id');

                    return data_get($byId->get($product), 'pending_reseller_evidence_count') === 1
                        && data_get($byId->get($emptyProduct['id']), 'pending_reseller_evidence_count') === 0
                        && ! $byId->has($foreignProduct)
                        && data_get($byId->get($product), 'commercial_order_id') === null
                        && data_get($byId->get($product), 'event_key_hash') === null
                        && data_get($byId->get($product), 'credits_delta') === null;
                }));
        $this->assertDatabaseCount('kslp_reseller_credit_ledger', 3);
        $this->assertDatabaseCount('kslp_licenses', 0);
    }

    public function test_ordinary_member_without_license_management_cannot_view_product_evidence(): void
    {
        $this->withoutVite();
        $owner = User::factory()->create(['email_verified_at' => now()]);
        $member = User::factory()->create(['email_verified_at' => now()]);
        [$org, $product, $order] = $this->issuer($owner, 'GAMMA');
        OrganizationMembership::query()->create([
            'organization_id' => $org,
            'user_id' => $member->id,
            'role' => 'member',
        ]);
        app(KslpResellerCreditEvidenceLedger::class)
            ->queuePending($owner->id, $org, $product, $order, 'pending:gamma:workspace');

        $this->actingAs($member)->get('/developer/apps')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('developer-apps')
                ->has('organizations', 0)
                ->has('applications', 0)
                ->has('keys', 0));
        $this->assertDatabaseCount('kslp_reseller_credit_ledger', 1);
        $this->assertDatabaseCount('kslp_licenses', 0);
    }
}
