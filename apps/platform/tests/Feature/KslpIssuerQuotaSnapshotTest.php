<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use App\Services\AuthorityBootstrapper;
use App\Services\Licensing\Kslp\KslpDeveloperWorkspaceQuery;
use App\Services\Licensing\Kslp\KslpIssuerSubscriptionAuthority;
use App\Services\Licensing\Kslp\KslpLicenseControlPlane;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

final class KslpIssuerQuotaSnapshotTest extends TestCase
{
    use RefreshDatabase;

    public function test_authorized_issuer_sees_exact_quota_consumption_without_other_tenant_data(): void
    {
        $owner = User::factory()->create(['email_verified_at' => now()]);
        $otherOwner = User::factory()->create(['email_verified_at' => now()]);

        $bootstrapper = app(AuthorityBootstrapper::class);
        $myOrg = (string) $bootstrapper->createOrganizationWithSandboxAccess('Issuer Org Alpha', $owner->id)->getKey();
        $otherOrg = (string) $bootstrapper->createOrganizationWithSandboxAccess('Issuer Org Beta', $otherOwner->id)->getKey();

        $authority = app(KslpIssuerSubscriptionAuthority::class);
        $authority->subscribe($myOrg, 'professional', 2, 3);
        $authority->subscribe($otherOrg, 'business', 10, 50);
        $authority->registerProduct($myOrg, 'ALPHA.APP', 'Alpha App');
        $authority->registerProduct($otherOrg, 'BETA.APP', 'Beta App');

        $control = app(KslpLicenseControlPlane::class);
        $control->issueDelegated($myOrg, 'alpha.customer', 'ALPHA.APP', 'trial', (string) $owner->id);
        $control->issueDelegated($otherOrg, 'beta.customer', 'BETA.APP', 'trial', (string) $otherOwner->id);

        $workspace = app(KslpDeveloperWorkspaceQuery::class)->forUser($owner);
        self::assertCount(1, $workspace['organizations']);

        $quota = $workspace['organizations'][0];
        self::assertSame($myOrg, $quota['id']);
        self::assertSame('active', $quota['issuer_status']);
        self::assertSame(2, $quota['product_limit']);
        self::assertSame(1, $quota['registered_products']);
        self::assertSame(1, $quota['product_remaining']);
        self::assertSame(3, $quota['monthly_issue_limit']);
        self::assertSame(1, $quota['monthly_issued']);
        self::assertSame(2, $quota['monthly_remaining']);
        self::assertCount(1, $workspace['applications']);
        self::assertSame($myOrg, $workspace['applications'][0]->organization_id);

        $json = json_encode($workspace, JSON_THROW_ON_ERROR);
        self::assertStringNotContainsString($otherOrg, $json);
        self::assertStringNotContainsString('BETA.APP', $json);
        self::assertStringNotContainsString('beta.customer', $json);
    }

    public function test_expired_issuer_shows_history_but_no_spendable_quota_or_credit(): void
    {
        $owner = User::factory()->create(['email_verified_at' => now()]);
        $organizationId = (string) app(AuthorityBootstrapper::class)
            ->createOrganizationWithSandboxAccess('Expired Issuer', $owner->id)->getKey();
        $authority = app(KslpIssuerSubscriptionAuthority::class);
        $authority->subscribe($organizationId, 'professional', 1, 2);
        $authority->registerProduct($organizationId, 'EXPIRED.APP', 'Expired App');

        app(KslpLicenseControlPlane::class)->issueDelegated(
            $organizationId, 'before.expiry', 'EXPIRED.APP', 'trial', (string) $owner->id
        );

        // Move the issuer policy to an expired state without changing any
        // existing license or adding a charge, wallet or new issuance.
        $authority->subscribe($organizationId, 'professional', 1, 2, now()->subMinute());

        $workspace = app(KslpDeveloperWorkspaceQuery::class)->forUser($owner);
        self::assertCount(1, $workspace['organizations']);
        $quota = $workspace['organizations'][0];

        self::assertSame('expired', $quota['issuer_status']);
        self::assertSame(1, $quota['registered_products']);
        self::assertSame(1, $quota['monthly_issued']);
        self::assertNull($quota['product_remaining']);
        self::assertNull($quota['monthly_remaining']);
    }
}
