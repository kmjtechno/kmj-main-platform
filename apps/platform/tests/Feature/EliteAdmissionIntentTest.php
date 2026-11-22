<?php

namespace Tests\Feature;

use App\Models\User;
use App\Services\Operations\EliteReleaseReadinessSnapshot;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\File;
use Illuminate\Testing\TestResponse;
use Tests\TestCase;

final class EliteAdmissionIntentTest extends TestCase
{
    use RefreshDatabase;

    private string $requestPath;

    private string $receiptPath;

    protected function setUp(): void
    {
        parent::setUp();

        $this->requestPath = storage_path('framework/testing/elite-admission-intent.json');
        $this->receiptPath = storage_path('framework/testing/elite-admission-proof.json');
        File::ensureDirectoryExists(dirname($this->requestPath), 0755, true);
        File::delete($this->requestPath);
        File::delete($this->receiptPath);
        config(['kmj.ops.admission_intent_path' => $this->requestPath]);
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

    private function installProof(array $overrides = []): void
    {
        $sha = str_repeat('a', 40);
        $proof = array_replace([
            'schema' => 'kmj.elite.release-readiness.v1',
            'host' => 'KMJ-elite',
            'source' => 'fixed_root_preflight',
            'captured_at_unix' => time(),
            'decision' => 'BLOCKED_ACCEPTANCE_SCHEMA',
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
        File::put($this->receiptPath, json_encode($proof, JSON_THROW_ON_ERROR));
        chmod($this->receiptPath, 0644);
        clearstatcache(true, $this->receiptPath);
        app()->instance(
            EliteReleaseReadinessSnapshot::class,
            new EliteReleaseReadinessSnapshot($this->receiptPath, (int) fileowner($this->receiptPath)),
        );
    }

    /** @return array<string, mixed> */
    private function request(): array
    {
        return [
            'approved_sha' => str_repeat('a', 40),
            'expected_current_release' => 'platform-'.str_repeat('b', 12),
            'confirmation' => 'REQUEST_RELEASE_ADMISSION',
            'owner_authenticated_qa_attested' => true,
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
            'credential_id' => 'release-admission-test-credential',
            'credential' => '{}',
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $owner;
    }

    private function submit(User $user, array $data): TestResponse
    {
        return $this->actingAs($user)
            ->withSession(['auth.password_confirmed_at' => time()])
            ->post('/operator/ops/actions/release-admission-intent', $data);
    }

    public function test_nonowner_cannot_create_admission_intent(): void
    {
        $this->installProof();
        $user = User::factory()->create(['email_verified_at' => now()]);

        $this->submit($user, $this->request())->assertForbidden();

        $this->assertFileDoesNotExist($this->requestPath);
        $this->assertDatabaseCount('operator_action_audits', 0);
    }

    public function test_owner_can_queue_only_an_intent_with_the_qa_attestation(): void
    {
        $this->installProof();
        $owner = $this->owner();

        $this->submit($owner, $this->request())->assertRedirect(route('operator.ops.index'));

        $intent = json_decode(File::get($this->requestPath), true, 16, JSON_THROW_ON_ERROR);
        $this->assertSame('kmj.elite.release-admission-intent.v1', $intent['schema']);
        $this->assertSame('write_release_admission', $intent['action']);
        $this->assertSame(str_repeat('a', 40), $intent['approved_sha']);
        $this->assertSame($owner->id, $intent['actor_user_id']);
        $this->assertTrue($intent['owner_authenticated_qa_attested']);
        $this->assertSame(90, $intent['expires_at_unix'] - $intent['created_at_unix']);
        $this->assertEqualsCanonicalizing([
            'schema', 'intent_id', 'actor_user_id', 'action', 'approved_sha',
            'expected_current_release', 'created_at_unix', 'expires_at_unix',
            'owner_authenticated_qa_attested',
        ], array_keys($intent));
        $this->assertDatabaseHas('operator_action_audits', [
            'actor_user_id' => $owner->id,
            'action' => 'release.admission_intent',
            'outcome' => 'queued_not_admitted',
        ]);
    }

    public function test_missing_or_false_attestation_and_bad_confirmation_never_queue(): void
    {
        $this->installProof();
        $owner = $this->owner();

        foreach ([
            ['owner_authenticated_qa_attested' => false],
            ['owner_authenticated_qa_attested' => null],
            ['confirmation' => 'REQUEST_APPROVED_PRODUCTION_RELEASE'],
            ['approved_sha' => 'latest'],
            ['expected_current_release' => 'arbitrary'],
        ] as $bad) {
            $this->submit($owner, array_replace($this->request(), $bad))->assertSessionHasErrors(array_key_first($bad));
            $this->assertFileDoesNotExist($this->requestPath);
        }
    }

    public function test_only_a_preflight_waiting_for_admission_can_queue(): void
    {
        $owner = $this->owner();

        foreach ([
            ['decision' => 'READY_APPROVED_RELEASE'],
            ['decision' => 'BLOCKED_STAGING_APPROVAL_DRIFT'],
            ['decision' => 'BLOCKED_ACCEPTANCE_EVIDENCE'],
            ['captured_at_unix' => time() - 300],
            ['current_release' => 'platform-'.str_repeat('c', 12)],
            ['host' => 'google-vps1'],
            ['deploy_triggered' => true],
        ] as $bad) {
            $this->installProof($bad);
            $this->submit($owner, $this->request())->assertStatus(409);
            $this->assertFileDoesNotExist($this->requestPath);
        }
    }

    public function test_wrong_sha_and_double_click_never_replace_a_pending_intent(): void
    {
        $this->installProof();
        $owner = $this->owner();

        $this->submit($owner, array_replace($this->request(), ['approved_sha' => str_repeat('c', 40)]))->assertStatus(409);
        $this->assertFileDoesNotExist($this->requestPath);

        $this->submit($owner, $this->request())->assertRedirect(route('operator.ops.index'));
        $old = File::get($this->requestPath);
        $this->submit($owner, $this->request())->assertStatus(409);
        $this->assertSame($old, File::get($this->requestPath));
    }

    public function test_symlink_inbox_is_never_overwritten(): void
    {
        if (PHP_OS_FAMILY === 'Windows' || ! function_exists('symlink')) {
            $this->markTestSkipped('POSIX inbox symlink defense.');
        }

        $this->installProof();
        $owner = $this->owner();
        if (! @symlink($this->requestPath.'.not-there', $this->requestPath)) {
            $this->markTestSkipped('Symlinks unavailable.');
        }
        $this->submit($owner, $this->request())->assertStatus(409);
        $this->assertTrue(is_link($this->requestPath));
    }
}
