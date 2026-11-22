<?php

declare(strict_types=1);

namespace Tests\Unit\AiProviders;

use App\Services\AiProviders\ModelCatalog;
use App\Services\AiProviders\RouteScorer;
use App\Services\AiProviders\TaskProfiler;
use PHPUnit\Framework\TestCase;

final class TaskRoutingTest extends TestCase
{
    public function test_profiler_separates_chat_coding_and_complex_work(): void
    {
        $profiler = new TaskProfiler;

        $this->assertSame('simple', $profiler->classify([['role' => 'user', 'content' => 'What is the capital of France?']]));
        $this->assertSame('coding', $profiler->classify([['role' => 'user', 'content' => "Fix this function in app.php:\n```php\nfunction a() {}\n```\n```\ntrace\n```"]]));
        $this->assertSame('complex', $profiler->classify([['role' => 'user', 'content' => 'Refactor the architecture across the codebase']]));
        $this->assertSame('complex', $profiler->classify([['role' => 'user', 'content' => 'hi']], 'tools'));
        $this->assertSame('complex', $profiler->classify([['role' => 'user', 'content' => str_repeat('x', 13000)]]));
    }

    public function test_scorer_sends_hard_work_to_strong_models_and_easy_work_to_light_ones(): void
    {
        $scorer = new RouteScorer(new ModelCatalog);
        $routes = [
            ['provider_id' => 'a', 'model' => 'llama-3.2-3b-instruct'],
            ['provider_id' => 'b', 'model' => 'qwen3-coder-480b'],
            ['provider_id' => 'c', 'model' => 'gpt-oss-20b'],
        ];
        $calm = static fn (string $id): array => ['low' => false, 'fails' => 0];

        $this->assertSame('qwen3-coder-480b', $scorer->order($routes, 'complex', $calm)[0]['model']);
        $this->assertSame('llama-3.2-3b-instruct', $scorer->order($routes, 'simple', $calm)[0]['model']);
        $this->assertSame('qwen3-coder-480b', $scorer->order($routes, 'coding', $calm)[0]['model']);
    }

    public function test_scorer_prefers_healthy_model_on_same_provider(): void
    {
        $scorer = new RouteScorer(new ModelCatalog);
        $routes = [
            ['provider_id' => 'groq-1', 'model' => 'free-model-a'],
            ['provider_id' => 'groq-1', 'model' => 'free-model-b'],
        ];
        $ordered = $scorer->order($routes, 'simple', static fn (string $id, string $model): array => [
            'low' => $model === 'free-model-a',
            'fails' => 0,
        ]);

        $this->assertSame('free-model-b', $ordered[0]['model']);
        $this->assertCount(2, $ordered);
    }

    public function test_scorer_sinks_routes_near_their_limit_and_never_adds_or_drops_a_route(): void
    {
        $scorer = new RouteScorer(new ModelCatalog);
        $routes = [
            ['provider_id' => 'a', 'model' => 'qwen3-coder-480b'],
            ['provider_id' => 'b', 'model' => 'kimi-k3'],
        ];

        $ordered = $scorer->order($routes, 'complex', static fn (string $id): array => ['low' => $id === 'a', 'fails' => 0]);

        $this->assertSame('b', $ordered[0]['provider_id']);
        $this->assertCount(2, $ordered);
        $this->assertEqualsCanonicalizing(['a', 'b'], array_column($ordered, 'provider_id'));
    }
}
