<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Http;
use Illuminate\Testing\TestResponse;
use Tests\TestCase;

final class EliteReleasePrepareIntentTest extends TestCase
{
    use RefreshDatabase;

    private string $requestPath;

    private string $statusPath;

    private string $sha;

    private mixed $mainResponse = null;

    protected function setUp(): void
    {
        parent::setUp();

        $this->sha = str_repeat('a', 40);
        $this->requestPath = storage_path('framework/testing/elite-prepare-intent.json');
        $this->statusPath = storage_path('framework/testing/elite-prepare-status.json');
        File::ensureDirectoryExists(dirname($this->requestPath), 0755, true);
        File::delete($this->requestPath);
        File::delete($this->statusPath);
        Cache::flush();
        config([
            'kmj.ops.prepare_intent_path' => $this->requestPath,
            'kmj.ops.prepare_status_path' => $this->statusPath,
        ]);
        $this->fakeMain($this->sha);
    }

    protected function tearDown(): void
    {
        if (is_link($this->requestPath)) {
            unlink($this->requestPath);
        } else {
            File::delete($this->requestPath);
        }
        File::delete($this->statusPath);
        parent::tearDown();
    }

    private function fakeMain(string $sha): void
    {
        $this->useMainResponse(Http::response(['sha' => $sha], 200));
    }

    /** Laravel keeps the first matching fake, so the stub reads a mutable response instead of re-faking. */
    private function useMainResponse(mixed $response): void
    {
        $first = $this->mainResponse === null;
        $this->mainResponse = $response;
        if ($first) {
            Http::fake(['api.github.com/*' => fn () => $this->mainResponse]);
        }
    }

    /** @return array<string, mixed> */
    private function request(): array
    {
        return [
            'approved_sha' => $this->sha,
            'confirmation' => 'REQUEST_RELEASE_PREPARE',
            'owner_backup_rollback_attested' => true,
            'migrate_after_activation_accepted' => true,
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
            'credential_id' => 'release-prepare-test-credential',
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
            ->post('/operator/ops/actions/release-prepare-intent', $data);
    }

    public function test_nonowner_cannot_create_prepare_intent(): void
    {
        $user = User::factory()->create(['email_verified_at' => now()]);

        $this->submit($user, $this->request())->assertForbidden();

        $this->assertFileDoesNotExist($this->requestPath);
        $this->assertDatabaseCount('operator_action_audits', 0);
    }

    public function test_owner_queues_only_an_exact_intent_with_both_attestations(): void
    {
        $owner = $this->owner();

        $this->submit($owner, $this->request())->assertRedirect(route('operator.ops.index'));

        $intent = json_decode(File::get($this->requestPath), true, 16, JSON_THROW_ON_ERROR);
        $this->assertSame('kmj.elite.release-prepare-intent.v1', $intent['schema']);
        $this->assertSame('prepare_release_candidate', $intent['action']);
        $this->assertSame($this->sha, $intent['approved_sha']);
        $this->assertSame($owner->id, $intent['actor_user_id']);
        $this->assertTrue($intent['owner_backup_rollback_attested']);
        $this->assertTrue($intent['migrate_after_activation_accepted']);
        $this->assertSame(90, $intent['expires_at_unix'] - $intent['created_at_unix']);
        $this->assertEqualsCanonicalizing([
            'schema', 'intent_id', 'actor_user_id', 'action', 'approved_sha',
            'created_at_unix', 'expires_at_unix',
            'owner_backup_rollback_attested', 'migrate_after_activation_accepted',
        ], array_keys($intent));
        $this->assertDatabaseHas('operator_action_audits', [
            'actor_user_id' => $owner->id,
            'action' => 'release.prepare_intent',
            'outcome' => 'queued_not_prepared',
        ]);
    }

    public function test_missing_attestation_bad_confirmation_or_bad_sha_never_queue(): void
    {
        $owner = $this->owner();

        foreach ([
            ['owner_backup_rollback_attested' => false],
            ['owner_backup_rollback_attested' => null],
            ['migrate_after_activation_accepted' => false],
            ['migrate_after_activation_accepted' => null],
            ['confirmation' => 'REQUEST_RELEASE_ADMISSION'],
            ['approved_sha' => 'latest'],
            ['approved_sha' => strtoupper($this->sha)],
        ] as $bad) {
            $this->submit($owner, array_replace($this->request(), $bad))->assertSessionHasErrors(array_key_first($bad));
            $this->assertFileDoesNotExist($this->requestPath);
        }
        $this->assertDatabaseCount('operator_action_audits', 0);
    }

    public function test_a_sha_that_is_not_the_verified_main_head_is_refused(): void
    {
        $owner = $this->owner();
        $this->fakeMain(str_repeat('c', 40));

        $this->submit($owner, $this->request())->assertStatus(409);

        $this->assertFileDoesNotExist($this->requestPath);
        $this->assertDatabaseCount('operator_action_audits', 0);
    }

    public function test_unverifiable_main_head_fails_closed(): void
    {
        $owner = $this->owner();
        $this->useMainResponse(Http::response('boom', 500));

        $this->submit($owner, $this->request())->assertStatus(409);
        $this->assertFileDoesNotExist($this->requestPath);

        Cache::flush();
        $this->useMainResponse(Http::response(['sha' => 'not-a-sha'], 200));
        $this->submit($owner, $this->request())->assertStatus(409);
        $this->assertFileDoesNotExist($this->requestPath);
    }

    public function test_pending_request_is_never_overwritten_and_dangling_link_is_refused(): void
    {
        $owner = $this->owner();
        File::put($this->requestPath, 'pending');

        $this->submit($owner, $this->request())->assertStatus(409);
        $this->assertSame('pending', File::get($this->requestPath));

        File::delete($this->requestPath);
        symlink('/tmp/kmj-prepare-intent-nowhere', $this->requestPath);
        $this->submit($owner, $this->request())->assertStatus(409);
        $this->assertTrue(is_link($this->requestPath));
    }

    public function test_ops_page_exposes_main_head_and_only_a_strictly_valid_status(): void
    {
        $owner = $this->owner();
        $valid = [
            'approved_sha' => $this->sha, 'detail' => 'approval written', 'schema' => 'kmj.elite.release-prepare-status.v1',
            'state' => 'prepared_awaiting_activation', 'updated_at_unix' => time(),
        ];
        File::put($this->statusPath, json_encode($valid, JSON_THROW_ON_ERROR));

        $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
            ->get('/operator/ops')
            ->assertOk()
            ->assertInertia(fn ($page) => $page
                ->where('releasePrepare.main_head', $this->sha)
                ->where('releasePrepare.status.state', 'prepared_awaiting_activation'));

        foreach ([
            array_replace($valid, ['state' => 'released_everything']),
            array_replace($valid, ['approved_sha' => 'x']),
            array_replace($valid, ['schema' => 'other']),
            array_replace($valid, ['detail' => str_repeat('x', 121)]),
            $valid + ['extra' => 1],
        ] as $bad) {
            File::put($this->statusPath, json_encode($bad, JSON_THROW_ON_ERROR));
            $this->actingAs($owner)->withSession(['auth.password_confirmed_at' => time()])
                ->get('/operator/ops')
                ->assertOk()
                ->assertInertia(fn ($page) => $page->where('releasePrepare.status', null));
        }
    }
}
