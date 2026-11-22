<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use App\Services\Operations\ReleaseContractCatalog;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\File;
use Tests\TestCase;

final class ReleaseCenterTest extends TestCase
{
    use RefreshDatabase;

    private string $dir;

    protected function setUp(): void
    {
        parent::setUp();
        $this->dir = storage_path('framework/testing/release-contracts');
        File::deleteDirectory($this->dir);
        File::ensureDirectoryExists($this->dir);
        config(['kmj.release.contracts_path' => $this->dir]);
    }

    protected function tearDown(): void
    {
        File::deleteDirectory($this->dir);
        parent::tearDown();
    }

    /** @return array<string, mixed> */
    private function contract(string $project = 'demo-app'): array
    {
        return [
            'schema_version' => 1, 'project' => $project, 'kind' => 'node-service',
            'repository' => 'kmjtechno/demo', 'default_branch' => 'main',
            'required_checks' => ['verify'], 'stage' => ['gate' => 'ci-verify'],
            'smoke' => ['probe' => 'gateway-health'], 'health' => ['probe' => 'live-sha'],
            'rollback' => ['strategy' => 'previous-release'], 'data_risk' => 'none',
            'approval' => 'owner-passkey', 'signing' => 'none',
        ];
    }

    private function writeContract(string $name, mixed $data): void
    {
        File::put($this->dir.'/'.$name, is_string($data) ? $data : json_encode($data, JSON_THROW_ON_ERROR));
    }

    public function test_regular_user_and_guest_cannot_open_the_release_center(): void
    {
        $this->get('/operator/release-center')->assertRedirect();
        $user = User::factory()->create(['email_verified_at' => now()]);
        $this->actingAs($user)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/release-center')->assertForbidden();
    }

    public function test_owner_sees_valid_contracts_and_nothing_else_is_exposed(): void
    {
        $this->writeContract('demo-app.release.contract.json', $this->contract());

        $this->actingAs($this->owner())->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/release-center')
            ->assertOk()
            ->assertInertia(fn ($page) => $page
                ->component('operator-release-center')
                ->where('catalog.status', 'ok')
                ->where('catalog.contracts.0.project', 'demo-app')
                ->where('catalog.contracts.0.approval', 'owner-passkey')
                ->where('catalog.invalid', []));
    }

    public function test_main_platform_live_status_is_advisory_and_degrades_without_a_receipt(): void
    {
        config(['kmj.ops.release_receipt_path' => $this->dir.'/no-such-receipt.json']);
        $this->writeContract('main-platform.release.contract.json', $this->contract('main-platform'));

        $this->actingAs($this->owner())->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/release-center')
            ->assertOk()
            ->assertInertia(fn ($page) => $page
                ->where('live.main-platform.readiness_status', 'unavailable')
                ->where('live.main-platform.approved_sha', null)
                ->has('live.main-platform.deployed_sha')
                ->missing('live.demo-app'));
    }

    public function test_relaxed_approval_wrong_filename_oversized_and_broken_files_are_listed_as_invalid(): void
    {
        $relaxed = $this->contract('relaxed');
        $relaxed['approval'] = 'auto';
        $this->writeContract('relaxed.release.contract.json', $relaxed);
        $this->writeContract('wrong-name.release.contract.json', $this->contract('other'));
        $this->writeContract('broken.release.contract.json', '{not json');
        $this->writeContract('big.release.contract.json', str_repeat(' ', 9000).json_encode($this->contract('big')));
        $this->writeContract('ok.release.contract.json', $this->contract('ok'));

        $catalog = (new ReleaseContractCatalog)->load($this->dir);

        $this->assertSame('ok', $catalog['status']);
        $this->assertSame(['ok'], array_column($catalog['contracts'], 'project'));
        $this->assertEqualsCanonicalizing(
            ['big.release.contract.json', 'broken.release.contract.json', 'relaxed.release.contract.json', 'wrong-name.release.contract.json'],
            $catalog['invalid'],
        );
    }

    public function test_missing_directory_is_unavailable_and_the_page_is_get_only(): void
    {
        $this->assertSame(
            ['status' => 'unavailable', 'contracts' => [], 'invalid' => []],
            (new ReleaseContractCatalog)->load($this->dir.'/missing'),
        );
        $owner = $this->owner();
        foreach (['post', 'put', 'patch', 'delete'] as $method) {
            $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
                ->{$method}('/operator/release-center')->assertStatus(405);
        }
    }

    public function test_committed_repository_contracts_all_load(): void
    {
        $catalog = (new ReleaseContractCatalog)->load(base_path('../../release/contracts'));

        $this->assertSame('ok', $catalog['status']);
        $this->assertSame([], $catalog['invalid']);
        $this->assertContains('main-platform', array_column($catalog['contracts'], 'project'));
        $this->assertContains('kmj-codebridge', array_column($catalog['contracts'], 'project'));
    }

    private function owner(): User
    {
        $user = User::factory()->create([
            'email_verified_at' => now(),
            'is_platform_owner' => true,
            'platform_owner_granted_at' => now(),
        ]);
        DB::table('passkeys')->insert([
            'user_id' => $user->id,
            'name' => 'Release center test passkey',
            'credential_id' => 'release-center-test-credential',
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $user;
    }
}
