<?php

declare(strict_types=1);

namespace Tests\Feature;

use App\Services\KnowledgeMemory\KnowledgeMemoryStore;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use InvalidArgumentException;
use Tests\TestCase;

final class KnowledgeMemoryStoreTest extends TestCase
{
    use RefreshDatabase;

    private string $orgA;

    private string $orgB;

    private KnowledgeMemoryStore $store;

    protected function setUp(): void
    {
        parent::setUp();
        $this->orgA = $this->organization();
        $this->orgB = $this->organization();
        $this->store = app(KnowledgeMemoryStore::class);
    }

    public function test_memories_are_explicitly_scoped_to_organization_and_project(): void
    {
        $saved = $this->store->save($this->orgA, 'kmj-codebridge', $this->input());

        $this->assertFalse($saved['replayed']);
        $this->assertSame(1, $saved['revision']);
        $this->assertSame('Prevent checkout reset on dirty worktrees', $this->store->get(
            $this->orgA, 'kmj-codebridge', $saved['observation_id']
        )['title']);

        $this->assertNull($this->store->get($this->orgB, 'kmj-codebridge', $saved['observation_id']));
        $this->assertNull($this->store->get($this->orgA, 'kmj-cinecore', $saved['observation_id']));
        $this->assertCount(0, $this->store->search($this->orgB, 'kmj-codebridge', 'dirty'));
        $this->assertCount(0, $this->store->search($this->orgA, 'kmj-cinecore', 'dirty'));
        $this->assertCount(1, $this->store->search($this->orgA, 'kmj-codebridge', 'dirty'));
    }

    public function test_exact_retry_returns_original_receipt_without_another_revision(): void
    {
        $input = $this->input();
        $first = $this->store->save($this->orgA, 'kmj-codebridge', $input);
        $second = $this->store->save($this->orgA, 'kmj-codebridge', $input);
        $this->assertTrue($second['replayed']);
        $this->assertSame($first['observation_id'], $second['observation_id']);
        $this->assertSame(1, $second['revision']);
        $this->assertDatabaseCount('knowledge_observations', 1);
        $this->assertDatabaseCount('knowledge_write_receipts', 1);
    }

    public function test_replaying_changed_payload_fails_closed_without_modification(): void
    {
        $first = $this->store->save($this->orgA, 'kmj-codebridge', $this->input());
        try {
            $this->store->save($this->orgA, 'kmj-codebridge', $this->input([
                'content' => 'Surprise overwrite.',
            ]));
            $this->fail('Reused operation key changed content');
        } catch (DomainException $e) {
            $this->assertSame('KNOWLEDGE_OPERATION_CONFLICT', $e->getMessage());
        }
        $this->assertSame(1, $this->store->get($this->orgA, 'kmj-codebridge', $first['observation_id'])['revision']);
        $this->assertDatabaseCount('knowledge_write_receipts', 1);
    }

    public function test_topic_updates_need_exact_prior_revision_and_keep_stable_identity(): void
    {
        $first = $this->store->save($this->orgA, 'kmj-codebridge', $this->input());
        $next = $this->store->save($this->orgA, 'kmj-codebridge', $this->input([
            'operation_id' => 'memory-operation-0002',
            'content' => 'Use an isolated worktree and an immutable baseline SHA.',
            'expected_revision' => 1,
        ]));
        $this->assertSame(2, $next['revision']);
        $this->assertSame($first['observation_id'], $next['observation_id']);
        $this->assertSame(2, $this->store->get($this->orgA, 'kmj-codebridge', $first['observation_id'])['revision']);

        try {
            $this->store->save($this->orgA, 'kmj-codebridge', $this->input([
                'operation_id' => 'memory-operation-0003',
                'expected_revision' => 1,
            ]));
            $this->fail('Stale revision was accepted');
        } catch (DomainException $e) {
            $this->assertSame('KNOWLEDGE_REVISION_CONFLICT', $e->getMessage());
        }
        $this->assertDatabaseCount('knowledge_write_receipts', 2);
    }

    public function test_existing_topic_cannot_be_silently_recreated(): void
    {
        $this->store->save($this->orgA, 'kmj-codebridge', $this->input());
        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('KNOWLEDGE_REVISION_CONFLICT');
        $this->store->save($this->orgA, 'kmj-codebridge', $this->input([
            'operation_id' => 'memory-operation-0002',
        ]));
    }

    public function test_scopes_allow_same_topic_and_operation_identifiers_without_collisions(): void
    {
        $a = $this->store->save($this->orgA, 'kmj-codebridge', $this->input());
        $b = $this->store->save($this->orgB, 'kmj-codebridge', $this->input());
        $c = $this->store->save($this->orgA, 'kmj-cinecore', $this->input());
        $this->assertNotSame($a['observation_id'], $b['observation_id']);
        $this->assertNotSame($a['observation_id'], $c['observation_id']);
        $this->assertDatabaseCount('knowledge_observations', 3);
        $this->assertDatabaseCount('knowledge_write_receipts', 3);
    }

    public function test_bounded_search_gives_preview_but_get_returns_full_observation(): void
    {
        $payload = $this->input(['content' => str_repeat('Safe historical finding. ', 30).' Keep dirty file safeguards.']);
        $saved = $this->store->save($this->orgA, 'kmj-codebridge', $payload);
        $rows = $this->store->search($this->orgA, 'kmj-codebridge', 'dirty', 1);
        $this->assertCount(1, $rows);
        $this->assertLessThan(strlen($payload['content']), strlen($rows[0]['preview']));
        $this->assertSame($payload['content'], $this->store->get(
            $this->orgA, 'kmj-codebridge', $saved['observation_id']
        )['content']);
    }

    public function test_suspicious_secrets_raw_prompts_and_invalid_filters_are_not_stored(): void
    {
        foreach ([
            $this->input(['content' => 'api_key=DO_NOT_STORE']),
            $this->input(['content' => '-----BEGIN '. 'RSA PRIVATE KEY-----']),
            $this->input(['content' => 'sk-proj-'.str_repeat('x', 24)]),
            $this->input(['title' => "Unexpected\nscript"]),
            $this->input(['expected_revision' => -1]),
            $this->input(['extra' => 'unexpected']),
        ] as $payload) {
            try {
                $this->store->save($this->orgA, 'kmj-codebridge', $payload);
                $this->fail('Unsafe payload was accepted');
            } catch (InvalidArgumentException) {
                $this->addToAssertionCount(1);
            }
        }
        $this->assertDatabaseCount('knowledge_observations', 0);
        $this->assertDatabaseCount('knowledge_write_receipts', 0);
        $this->expectException(InvalidArgumentException::class);
        $this->store->search($this->orgA, 'kmj-codebridge', 'a%');
    }

    public function test_multiline_observation_is_sanitized_only_in_compact_search_preview(): void
    {
        $fullText = "Use the isolated QA cluster.\nKeep the original evidence intact.\tNever execute notes.";
        $saved = $this->store->save($this->orgA, 'kmj-codebridge', $this->input([
            'content' => $fullText,
        ]));

        $rows = $this->store->search($this->orgA, 'kmj-codebridge', 'isolated');
        $this->assertCount(1, $rows);
        $this->assertSame($this->orgA, $rows[0]['organization_id']);
        $this->assertSame('kmj-codebridge', $rows[0]['project_key']);
        $this->assertStringNotContainsString("\n", $rows[0]['preview']);
        $this->assertStringNotContainsString("\t", $rows[0]['preview']);
        $this->assertStringContainsString('Keep the original evidence', $rows[0]['preview']);
        $this->assertSame($fullText, $this->store->get(
            $this->orgA, 'kmj-codebridge', $saved['observation_id']
        )['content']);
    }

    public function test_invalid_project_and_unknown_observation_id_fail_closed(): void
    {
        $this->assertNull($this->store->get($this->orgA, 'kmj-codebridge', (string) Str::uuid()));
        $this->expectException(InvalidArgumentException::class);
        $this->store->search($this->orgA, '../other-project', 'checkout');
    }

    /** @param array<string, mixed> $replace
     *  @return array<string, mixed>
     */
    private function input(array $replace = []): array
    {
        return array_replace([
            'operation_id' => 'memory-operation-0001',
            'topic_key' => 'decision/dirty-worktree',
            'type' => 'decision',
            'title' => 'Prevent checkout reset on dirty worktrees',
            'content' => 'Never reset the current dirty checkout. Use isolated worktrees.',
            'expected_revision' => 0,
        ], $replace);
    }

    private function organization(): string
    {
        $id = (string) Str::uuid();
        DB::table('organizations')->insert([
            'id' => $id,
            'name' => 'Org '.Str::random(7),
            'created_at' => now(),
            'updated_at' => now(),
        ]);

        return $id;
    }
}
