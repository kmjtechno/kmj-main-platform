<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Models\User;
use App\Services\AiProviders\ResolvesAiProviderScope;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Tests\Support\FakeAiProviderScope;
use Tests\TestCase;

final class KnowledgeMemoryControllerTest extends TestCase
{
    use RefreshDatabase;

    private User $owner;

    private User $reader;

    private User $outsider;

    private string $organizationA;

    private string $organizationB;

    protected function setUp(): void
    {
        parent::setUp();
        $this->organizationA = $this->organization();
        $this->organizationB = $this->organization();
        $this->owner = User::factory()->create(['email_verified_at' => now()]);
        $this->reader = User::factory()->create(['email_verified_at' => now()]);
        $this->outsider = User::factory()->create(['email_verified_at' => now()]);
        $this->app->instance(ResolvesAiProviderScope::class, new FakeAiProviderScope([
            $this->owner->id => ['organization_id' => $this->organizationA, 'can_manage' => true],
            $this->reader->id => ['organization_id' => $this->organizationA, 'can_manage' => false],
            $this->outsider->id => ['organization_id' => $this->organizationB, 'can_manage' => true],
        ]));
    }

    public function test_default_disabled_responds_with_not_found_without_writing(): void
    {
        config(['knowledge_memory.enabled' => false]);
        $url = '/services/kmj-codebridge/knowledge-memory';
        $this->actingAs($this->owner)->getJson($url.'?query=dirty')->assertNotFound();
        $this->confirmed($this->owner)->postJson($url, $this->memory())->assertNotFound();
        $this->assertDatabaseCount('knowledge_observations', 0);
    }

    public function test_unauthenticated_cannot_read_or_write_even_when_enabled(): void
    {
        config(['knowledge_memory.enabled' => true]);
        $url = '/services/kmj-codebridge/knowledge-memory';
        $this->getJson($url.'?query=dirty')->assertUnauthorized();
        $this->postJson($url, $this->memory())->assertUnauthorized();
        $this->assertDatabaseCount('knowledge_observations', 0);
    }

    public function test_owner_can_explicitly_save_and_member_can_retrieve_but_not_write(): void
    {
        config(['knowledge_memory.enabled' => true]);
        $url = '/services/kmj-codebridge/knowledge-memory';

        $created = $this->confirmed($this->owner)->postJson($url, $this->memory())
            ->assertCreated()
            ->assertJsonPath('revision', 1)
            ->assertJsonPath('replayed', false);
        $id = $created->json('observation_id');

        $this->actingAs($this->reader)->getJson($url.'?query=dirty')
            ->assertOk()
            ->assertJsonPath('observations.0.topic_key', 'decision/dirty-worktree')
            ->assertJsonPath('observations.0.project_key', 'kmj-codebridge')
            ->assertHeader('Cache-Control', 'private, no-store');

        $this->actingAs($this->reader)->getJson($url.'/'.$id)
            ->assertOk()
            ->assertJsonPath('observation.content', 'Preserve uncommitted changes; use isolated worktrees.');

        $this->confirmed($this->reader)->postJson($url, $this->memory([
            'operation_id' => 'unique-operation-0002',
        ]))->assertForbidden();
        $this->assertDatabaseCount('knowledge_observations', 1);
    }

    public function test_outsider_cannot_read_foreign_tenant_or_claim_another_project(): void
    {
        config(['knowledge_memory.enabled' => true]);
        $url = '/services/kmj-codebridge/knowledge-memory';
        $id = $this->confirmed($this->owner)->postJson($url, $this->memory())
            ->assertCreated()->json('observation_id');

        $this->actingAs($this->outsider)->getJson($url.'?query=dirty')
            ->assertOk()->assertJsonCount(0, 'observations');
        $this->actingAs($this->outsider)->getJson($url.'/'.$id)->assertNotFound();

        $this->confirmed($this->outsider)->postJson($url, $this->memory([
            'operation_id' => 'unique-operation-0003',
            'project' => 'kmj-cinecore',
            'organization_id' => $this->organizationA,
        ]))->assertUnprocessable()->assertJsonValidationErrors('scope');

        // A scope-spoofing request must not create records in either tenant.
        $this->assertDatabaseCount('knowledge_observations', 1);

        // An authorized B-owner can create only in the fixed CodeBridge
        // project of their own tenant when providing no scope override.
        $this->confirmed($this->outsider)->postJson($url, $this->memory([
            'operation_id' => 'unique-operation-0004',
        ]))->assertCreated();
        $this->assertDatabaseHas('knowledge_observations', [
            'organization_id' => $this->organizationB,
            'project_key' => 'kmj-codebridge',
        ]);
        $this->assertDatabaseMissing('knowledge_observations', [
            'organization_id' => $this->organizationA,
            'project_key' => 'kmj-cinecore',
        ]);
    }

    public function test_write_requires_recent_password_confirmation_and_retries_are_idempotent(): void
    {
        config(['knowledge_memory.enabled' => true]);
        $url = '/services/kmj-codebridge/knowledge-memory';
        $this->actingAs($this->owner)->postJson($url, $this->memory())->assertStatus(423);

        $created = $this->confirmed($this->owner)->postJson($url, $this->memory())->assertCreated();
        $same = $this->confirmed($this->owner)->postJson($url, $this->memory())
            ->assertOk()->assertJsonPath('replayed', true);
        $this->assertSame($created->json('observation_id'), $same->json('observation_id'));

        $this->confirmed($this->owner)->postJson($url, $this->memory([
            'content' => 'Unexpected revised content.',
        ]))->assertStatus(409)->assertJsonPath('error', 'KNOWLEDGE_OPERATION_CONFLICT');
        $this->assertDatabaseCount('knowledge_observations', 1);
        $this->assertDatabaseCount('knowledge_write_receipts', 1);
    }

    public function test_unsafe_content_and_search_query_fail_validation(): void
    {
        config(['knowledge_memory.enabled' => true]);
        $url = '/services/kmj-codebridge/knowledge-memory';
        $this->confirmed($this->owner)->postJson($url, $this->memory([
            'content' => 'api_key=DO_NOT_SHARE',
        ]))->assertUnprocessable()->assertJsonValidationErrors('content');
        $this->actingAs($this->owner)->getJson($url.'?query=bad%25wildcard')
            ->assertUnprocessable();
        $this->assertDatabaseCount('knowledge_observations', 0);
    }

    /** @param array<string, mixed> $replace
     *  @return array<string, mixed>
     */
    private function memory(array $replace = []): array
    {
        return array_replace([
            'operation_id' => 'unique-operation-0001',
            'topic_key' => 'decision/dirty-worktree',
            'type' => 'decision',
            'title' => 'Preserve dirty checkout',
            'content' => 'Preserve uncommitted changes; use isolated worktrees.',
            'expected_revision' => 0,
        ], $replace);
    }

    private function confirmed(User $user): static
    {
        return $this->actingAs($user)->withSession(['auth.password_confirmed_at' => time()]);
    }

    private function organization(): string
    {
        $id = (string) Str::uuid();
        DB::table('organizations')->insert([
            'id' => $id,
            'name' => 'Memory Org '.Str::random(7),
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $id;
    }
}
