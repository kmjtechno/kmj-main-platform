<?php

namespace Tests\Feature;

use App\Models\User;
use App\Services\AuthorityBootstrapper;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Storage;
use Inertia\Testing\AssertableInertia as Assert;
use KMJ\MainPlatform\Entitlements\Models\Entitlement;
use KMJ\MainPlatform\Releases\Services\ReleaseRegistry;
use Tests\TestCase;

final class CustomerReleaseDownloadTest extends TestCase
{
    use RefreshDatabase;

    public function test_dashboard_exposes_promoted_release_for_effective_customer_entitlement(): void
    {
        [$user, $releaseId, $digest] = $this->promotedReleaseFixture();

        $this->actingAs($user)
            ->get('/dashboard')
            ->assertOk()
            ->assertInertia(fn (Assert $page) => $page
                ->where('organizations.0.entitlements.0.release.id', $releaseId)
                ->where('organizations.0.entitlements.0.release.version', '1.2.3')
                ->where('organizations.0.entitlements.0.release.digest', $digest)
                ->where(
                    'organizations.0.entitlements.0.release.download_url',
                    '/customer/releases/'.$releaseId.'/download',
                ));
    }

    public function test_entitled_customer_can_download_promoted_artifact_after_digest_verification(): void
    {
        [$user, $releaseId, $digest] = $this->promotedReleaseFixture();

        $this->actingAs($user)
            ->get('/customer/releases/'.$releaseId.'/download')
            ->assertOk()
            ->assertDownload('kmj-release.bin')
            ->assertHeader('X-KMJ-Artifact-SHA256', $digest)
            ->assertHeader('Cache-Control', 'no-store, private');
    }

    public function test_release_download_fails_closed_for_unentitled_user_and_tampered_artifact(): void
    {
        [$user, $releaseId] = $this->promotedReleaseFixture();
        $otherUser = User::factory()->create(['email_verified_at' => now()]);

        $this->actingAs($otherUser)
            ->get('/customer/releases/'.$releaseId.'/download')
            ->assertNotFound();

        Storage::disk('local')->put('releases/kmj-release.bin', 'tampered');

        $this->actingAs($user)
            ->get('/customer/releases/'.$releaseId.'/download')
            ->assertServiceUnavailable();
    }

    /**
     * @return array{0: User, 1: string, 2: string}
     */
    private function promotedReleaseFixture(): array
    {
        Storage::fake('local');

        $user = User::factory()->create(['email_verified_at' => now()]);
        $organization = app(AuthorityBootstrapper::class)
            ->createOrganizationWithSandboxAccess('Release Customer', $user->id);

        $entitlement = Entitlement::query()
            ->where('organization_id', $organization->getKey())
            ->where('status', 'active')
            ->firstOrFail();

        $contents = 'verified-kmj-release-artifact';
        $digest = 'sha256:'.hash('sha256', $contents);
        Storage::disk('local')->put('releases/kmj-release.bin', $contents);

        $registry = app(ReleaseRegistry::class);
        $release = $registry->stage(
            (string) $entitlement->product_id,
            '1.2.3',
            $digest,
            'test:customer-release-download',
            'kmj-release.bin',
            'local',
            'releases/kmj-release.bin',
            'application/octet-stream',
            strlen($contents),
        );
        $release = $registry->promote((string) $release->getKey());

        return [$user, (string) $release->getKey(), $digest];
    }
}
