<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use App\Services\Licensing\Kslp\KslpIssuerSubscriptionAuthority;
use App\Services\Licensing\Kslp\KslpResellerReviewGrantAuthority;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use KMJ\MainPlatform\Organizations\Models\OrganizationMembership;
use KMJ\MainPlatform\Organizations\Services\OrganizationCapabilityContext;
use KMJ\MainPlatform\Organizations\Services\OrganizationCreator;
use Tests\TestCase;

final class KslpResellerReviewGrantAuthorityTest extends TestCase
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
            'name' => 'Reseller review owner',
            'credential_id' => 'reseller-owner-'.Str::uuid(),
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $owner;
    }

    /** @return array{0: string, 1: string, 2: string} */
    private function issuer(User $owner, User $member, string $suffix): array
    {
        $organization = app(OrganizationCreator::class)->create('Reviewer issuer '.$suffix, $owner->id);
        $org = (string) $organization->getKey();
        OrganizationMembership::query()->create([
            'organization_id' => $org,
            'user_id' => $member->id,
            'role' => 'member',
        ]);
        $authority = app(KslpIssuerSubscriptionAuthority::class);
        $authority->subscribe($org, 'professional', 2, 10);
        $first = $authority->registerProduct($org, 'REVIEW.'.$suffix.'.ONE', 'First '.$suffix);
        $second = $authority->registerProduct($org, 'REVIEW.'.$suffix.'.TWO', 'Second '.$suffix);

        return [$org, (string) $first['id'], (string) $second['id']];
    }

    public function test_owner_grant_is_explicit_product_scoped_and_review_only(): void
    {
        $owner = $this->owner();
        $member = User::factory()->create(['email_verified_at' => now()]);
        [$org, $first, $second] = $this->issuer($owner, $member, 'ALPHA');
        $grants = app(KslpResellerReviewGrantAuthority::class);
        self::assertFalse($grants->allowsReview($member->id, $org, $first));
        $grant = $grants->grant($owner->id, $org, $first, $member->id, now()->addDays(5), 'Approved scope for evidence review');
        self::assertSame('funding_evidence_review', $grant['permission']);
        self::assertFalse($grant['paid_issuance_enabled']);
        self::assertTrue($grants->allowsReview($member->id, $org, $first));
        self::assertFalse($grants->allowsReview($member->id, $org, $second));
        self::assertFalse(app(OrganizationCapabilityContext::class)->allows($member->id, $org, 'license.manage'));
        $this->assertDatabaseHas('license_audit_events', [
            'actor_id' => $owner->id,
            'organization_id' => $org,
            'action' => 'kslp_reseller_review_granted',
        ]);

        $grants->revoke($owner->id, $org, $first, $member->id, 'Review authorization withdrawn');
        $grants->revoke($owner->id, $org, $first, $member->id, 'Review authorization withdrawn');
        self::assertFalse($grants->allowsReview($member->id, $org, $first));
        self::assertSame(1, DB::table('license_audit_events')->where('action', 'kslp_reseller_review_revoked')->count());
        $this->assertDatabaseCount('kslp_licenses', 0);
        $this->assertDatabaseCount('kslp_reseller_credit_ledger', 0);
    }

    public function test_ordinary_issuer_owner_cannot_approve_reseller_grant(): void
    {
        $owner = User::factory()->create(['email_verified_at' => now()]);
        $member = User::factory()->create(['email_verified_at' => now()]);
        [$org, $first] = $this->issuer($owner, $member, 'BETA');
        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('KSLP_RESELLER_GRANT_OWNER_REQUIRED');

        app(KslpResellerReviewGrantAuthority::class)
            ->grant($owner->id, $org, $first, $member->id, now()->addDays(5), 'Unapproved issuer delegation');
    }

    public function test_expiry_pause_and_recreated_membership_fail_closed(): void
    {
        $owner = $this->owner();
        $member = User::factory()->create(['email_verified_at' => now()]);
        [$org, $first, $second] = $this->issuer($owner, $member, 'GAMMA');
        $grants = app(KslpResellerReviewGrantAuthority::class);
        $grants->grant($owner->id, $org, $first, $member->id, now()->addDays(5), 'Review first application');
        $grants->grant($owner->id, $org, $second, $member->id, now()->addDays(5), 'Review second application');

        DB::table('kslp_reseller_review_grants')->where('licensed_product_id', $first)
            ->update(['expires_at' => now()->subMinute()]);
        self::assertFalse($grants->allowsReview($member->id, $org, $first));
        DB::table('kslp_licensed_products')->where('id', $second)->update(['status' => 'paused']);
        self::assertFalse($grants->allowsReview($member->id, $org, $second));
        DB::table('kslp_licensed_products')->where('id', $second)->update(['status' => 'active']);
        self::assertTrue($grants->allowsReview($member->id, $org, $second));

        OrganizationMembership::query()->where('organization_id', $org)->where('user_id', $member->id)->delete();
        OrganizationMembership::query()->create([
            'organization_id' => $org,
            'user_id' => $member->id,
            'role' => 'member',
        ]);
        self::assertFalse($grants->allowsReview($member->id, $org, $second));
    }

    public function test_foreign_product_cannot_be_granted_to_local_member(): void
    {
        $owner = $this->owner();
        $member = User::factory()->create(['email_verified_at' => now()]);
        $other = User::factory()->create(['email_verified_at' => now()]);
        [$org] = $this->issuer($owner, $member, 'DELTA');
        [, $foreign] = $this->issuer($owner, $other, 'EPSILON');

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('KSLP_RESELLER_PRODUCT_NOT_AUTHORIZED');

        app(KslpResellerReviewGrantAuthority::class)
            ->grant($owner->id, $org, $foreign, $member->id, now()->addDays(5), 'Attempt foreign product review');
    }
}
