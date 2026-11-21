<?php

namespace Tests\Feature;

use App\Models\User;
use App\Services\Operations\EliteReleaseReadinessSnapshot;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\File;
use Tests\TestCase;

final class EliteActivationIntentTest extends TestCase
{
    use RefreshDatabase;

    private string $requestPath;

    private string $receiptPath;

    protected function setUp(): void
    {
        parent::setUp();

        $this->requestPath = storage_path('framework/testing/elite-activation-intent.json');
        $this->receiptPath = storage_path('framework/testing/elite-activation-proof.json');
        File::ensureDirectoryExists(dirname($this->requestPath), 0755, true);
        File::delete($this->requestPath);
        File::delete($this->receiptPath);
        config(['kmj.ops.activation_intent_path' => $this->requestPath]);
    }

    protected function tearDown(): void
    {
        if (is_link($this->requestPath)) {
            unlink($this->requestPath);
        } else {
            File::delete($this->requestPath);
        }
        File::delete($this->receiptPath);
        parent::tearDown();
    }

    /** @return array<string, mixed> */
    private function proof(array $overrides = []): array
    {
        $sha = str_repeat('a', 40);

        return array_replace([
            'schema' => 'kmj.elite.release-readiness.v1',
            'host' => 'KMJ-elite',
            'source' => 'fixed_root_preflight',
            'captured_at_unix' => time(),
            'decision' => 'READY_APPROVED_RELEASE',
            'current_release' => 'platform-'.str_repeat('b', 12),
            'approved_sha' => $sha,
            'expected_current_release' => 'platform-'.str_repeat('b', 12),
            'promoted_sha' => $sha,
            'candidate_sha' => $sha,
            'staging_origin_verified' => false,
            'scheduled_run_proven' => false,
            'independent_dr_verified' => false,
            'deploy_triggered' => false,
        ], $overrides);
    }

    private function installSyntheticTrustedProof(array $overrides = []): void
    {
        File::put($this->receiptPath, json_encode($this->proof($overrides), JSON_THROW_ON_ERROR));
        chmod($this->receiptPath, 0644);
        clearstatcache(true, $this->receiptPath);
        app()->instance(
            EliteReleaseReadinessSnapshot::class,
            new EliteReleaseReadinessSnapshot($this->receiptPath, (int) fileowner($this->receiptPath)),
        );
    }

    /** @return array<string, string> */
    private function request(): array
    {
        return [
            'approved_sha' => str_repeat('a', 40),
            'expected_current_release' => 'platform-'.str_repeat('b', 12),
            'confirmation' => 'REQUEST_APPROVED_PRODUCTION_RELEASE',
        ];
    }

    private function owner(): User
    {
        $owner = User::factory()->create([
            'email_verified_at' => now(),
            'is_platform_owner' => true,
            'platform_owner_granted_at' => now(),
        ]);
        DB::table('passkeys')->insert([
            'user_id' => $owner->id,
            'name' => 'Release owner passkey',
            'credential_id' => 'release-activation-test-credential',
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $owner;
    }

    public function test_nonowner_cannot_create_production_activation_intent(): void
    {
        $this->installSyntheticTrustedProof();
        $user = User::factory()->create(['email_verified_at' => now()]);

        $this->actingAs($user)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/ops/actions/release-activation-intent', $this->request())
            ->assertForbidden();

        $this->assertFileDoesNotExist($this->requestPath);
        $this->assertDatabaseCount('operator_action_audits', 0);
    }

    public function test_owner_with_verified_exact_preflight_can_only_queue_not_deploy(): void
    {
        $this->installSyntheticTrustedProof();
        $owner = $this->owner();

        $this->actingAs($owner)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/ops/actions/release-activation-intent', $this->request())
            ->assertRedirect(route('operator.ops.index'));

        $this->assertFileExists($this->requestPath);
        $intent = json_decode(File::get($this->requestPath), true, 16, JSON_THROW_ON_ERROR);
        $this->assertSame('kmj.elite.production-activation-intent.v1', $intent['schema']);
        $this->assertSame('activate_existing_approved_release', $intent['action']);
        $this->assertSame($this->request()['approved_sha'], $intent['approved_sha']);
        $this->assertSame($this->request()['expected_current_release'], $intent['expected_current_release']);
        $this->assertSame($owner->id, $intent['actor_user_id']);
        $this->assertSame(90, $intent['expires_at_unix'] - $intent['created_at_unix']);
        $this->assertArrayNotHasKey('shell', $intent);
        $this->assertArrayNotHasKey('release_activated', $intent);

        $this->assertDatabaseHas('operator_action_audits', [
            'actor_user_id' => $owner->id,
            'action' => 'release.activation_intent',
            'outcome' => 'queued_not_deployed',
        ]);
    }

    public function test_double_click_never_replaces_pending_exact_intent(): void
    {
        $this->installSyntheticTrustedProof();
        $owner = $this->owner();
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/ops/actions/release-activation-intent', $this->request())
            ->assertRedirect(route('operator.ops.index'));

        $old = File::get($this->requestPath);
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/ops/actions/release-activation-intent', $this->request())
            ->assertStatus(409);

        $this->assertSame($old, File::get($this->requestPath));
        $this->assertDatabaseHas('operator_action_audits', [
            'actor_user_id' => $owner->id,
            'action' => 'release.activation_intent',
            'outcome' => 'queued_not_deployed',
        ]);
    }

    public function test_expired_or_contradictory_root_proof_never_queues(): void
    {
        $owner = $this->owner();

        foreach ([
            ['captured_at_unix' => time() - 300],
            ['current_release' => 'platform-'.str_repeat('c', 12)],
            ['candidate_sha' => str_repeat('c', 40)],
            ['promoted_sha' => str_repeat('c', 40)],
            ['host' => 'google-vps1'],
            ['decision' => 'BLOCKED_CURRENT_RELEASE_DRIFT'],
            ['deploy_triggered' => true],
        ] as $bad) {
            $this->installSyntheticTrustedProof($bad);
            $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
                ->post('/operator/ops/actions/release-activation-intent', $this->request())
                ->assertStatus(409);
            $this->assertFileDoesNotExist($this->requestPath);
        }
    }

    public function test_bad_shape_or_invented_confirm_action_fails_validation(): void
    {
        $this->installSyntheticTrustedProof();
        $owner = $this->owner();

        foreach ([
            ['approved_sha' => 'latest'],
            ['expected_current_release' => 'arbitrary-current'],
            ['confirmation' => 'FORCE_DEPLOY'],
        ] as $bad) {
            $field = array_key_first($bad);
            $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
                ->post('/operator/ops/actions/release-activation-intent', array_replace($this->request(), $bad))
                ->assertSessionHasErrors($field);
            $this->assertFileDoesNotExist($this->requestPath);
        }
    }

    public function test_well_shaped_but_incorrect_exact_sha_fails_preflight(): void
    {
        $this->installSyntheticTrustedProof();
        $owner = $this->owner();

        foreach ([
            ['approved_sha' => str_repeat('c', 40)],
            ['expected_current_release' => 'platform-'.str_repeat('c', 12)],
        ] as $bad) {
            $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
                ->post('/operator/ops/actions/release-activation-intent', array_replace($this->request(), $bad))
                ->assertStatus(409);
            $this->assertFileDoesNotExist($this->requestPath);
        }
    }

    public function test_symlink_existing_inbox_never_overwritten(): void
    {
        if (PHP_OS_FAMILY === 'Windows' || ! function_exists('symlink')) {
            $this->markTestSkipped('POSIX inbox symlink defense.');
        }

        $this->installSyntheticTrustedProof();
        $owner = $this->owner();
        $target = $this->requestPath.'.not-there';
        if (! @symlink($target, $this->requestPath)) {
            $this->markTestSkipped('Symlinks unavailable.');
        }
        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/ops/actions/release-activation-intent', $this->request())
            ->assertStatus(409);
        $this->assertTrue(is_link($this->requestPath));
    }
}
