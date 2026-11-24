<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use App\Services\Licensing\Kslp\KslpIssuerSubscriptionAuthority;
use App\Services\Licensing\Kslp\KslpResellerReviewGrantAuthority;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Inertia\Testing\AssertableInertia as Assert;
use KMJ\MainPlatform\Organizations\Models\OrganizationMembership;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;
use Tests\TestCase;

final class KslpOwnerResellerReviewManagementTest extends TestCase
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
            'name' => 'Review management owner',
            'credential_id' => 'review-management-'.Str::uuid(),
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $owner;
    }

    /** @return array{organization_id: string, product_id: string, reseller_user_id: int, days: int, reason: string} */
    private function scope(User $owner, User $member): array
    {
        $organization = app(OrganizationCreator::class)->create('Review management issuer', $owner->id);
        $org = (string) $organization->getKey();
        OrganizationMembership::query()->create([
            'organization_id' => $org,
            'user_id' => $member->id,
            'role' => 'member',
        ]);
        $issuer = app(KslpIssuerSubscriptionAuthority::class);
        $issuer->subscribe($org, 'professional', 2, 10);
        $product = $issuer->registerProduct($org, 'REVIEW.MANAGEMENT', 'Review management app');

        return [
            'organization_id' => $org,
            'product_id' => (string) $product['id'],
            'reseller_user_id' => $member->id,
            'days' => 30,
            'reason' => 'Approved evidence review only',
        ];
    }

    public function test_only_owner_with_step_up_can_create_grants_and_new_grants_default_off(): void
    {
        $this->withoutVite();
        $owner = $this->owner();
        $member = User::factory()->create(['email_verified_at' => now()]);
        $scope = $this->scope($owner, $member);

        config()->set('services.kmj_reseller_review.grant_enabled', false);
        $this->actingAs($member)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/kslp/reseller-review/grants', $scope)->assertForbidden();
        $this->get('/operator/kslp')->assertForbidden();

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/kslp/reseller-review/grants', $scope)->assertStatus(503);

        config()->set('services.kmj_reseller_review.grant_enabled', true);
        $this->withSession(['auth.password_confirmed_at' => 0])
            ->post('/operator/kslp/reseller-review/grants', $scope)->assertRedirect();
        $this->assertDatabaseCount('kslp_reseller_review_grants', 0);
        $this->assertDatabaseCount('kslp_licenses', 0);
        $this->assertDatabaseCount('kslp_reseller_credit_ledger', 0);
    }

    public function test_owner_directory_grant_and_revoke_reuse_the_existing_authority_without_paid_rights(): void
    {
        $this->withoutVite();
        $owner = $this->owner();
        $member = User::factory()->create(['email_verified_at' => now()]);
        $scope = $this->scope($owner, $member);
        config()->set('services.kmj_reseller_review.grant_enabled', true);

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/kslp')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->component('operator-kslp')
                ->where('resellerReviewDirectory.schema_ready', true)
                ->where('resellerReviewDirectory.grant_enabled', true)
                ->has('resellerReviewDirectory.candidates', 1)
                ->where('resellerReviewDirectory.candidates.0.product_id', $scope['product_id'])
                ->where('resellerReviewDirectory.candidates.0.reseller_user_id', (string) $member->id)
                ->has('resellerReviewDirectory.grants', 0));

        $this->post('/operator/kslp/reseller-review/grants', $scope)
            ->assertRedirect('/operator/kslp#reseller-review-management');
        $grantId = (string) DB::table('kslp_reseller_review_grants')->value('id');
        self::assertNotSame('', $grantId);
        $authority = app(KslpResellerReviewGrantAuthority::class);
        self::assertTrue($authority->allowsReview($member->id, $scope['organization_id'], $scope['product_id']));

        $this->get('/operator/kslp')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->has('resellerReviewDirectory.candidates', 0)
                ->has('resellerReviewDirectory.grants', 1)
                ->where('resellerReviewDirectory.grants.0.id', $grantId)
                ->where('resellerReviewDirectory.grants.0.revoked_at', null));

        config()->set('services.kmj_reseller_review.grant_enabled', false);
        $url = '/operator/kslp/reseller-review/grants/'.$grantId.'/revoke';
        $this->actingAs($member)->withSession(['auth.password_confirmed_at' => time()])
            ->post($url, ['reason' => 'Attempt unauthorized revocation'])->assertForbidden();
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post($url, ['reason' => 'Withdraw review authorization'])
            ->assertRedirect('/operator/kslp#reseller-review-management');
        self::assertFalse($authority->allowsReview($member->id, $scope['organization_id'], $scope['product_id']));
        $this->assertDatabaseHas('license_audit_events', [
            'actor_id' => $owner->id,
            'organization_id' => $scope['organization_id'],
            'action' => 'kslp_reseller_review_revoked',
        ]);
        $this->assertDatabaseCount('kslp_reseller_review_grants', 1);
        $this->assertDatabaseCount('kslp_licenses', 0);
        $this->assertDatabaseCount('kslp_reseller_credit_ledger', 0);
    }
}
