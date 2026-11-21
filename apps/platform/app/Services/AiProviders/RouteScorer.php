<?php

declare(strict_types=1);

namespace App\Services\AiProviders;

/**
 * Orders ALREADY ELIGIBLE routes for a task. It cannot add a route, so it can never reach a model
 * that the verified-zero planner did not admit. Easy work goes to lighter models so strong-model
 * quota is kept for hard work; routes that are about to hit their limit or keep failing sink
 * before they actually run out.
 */
final class RouteScorer
{
    public function __construct(private readonly ModelCatalog $catalog) {}

    /**
     * @param  list<array<string, mixed>>  $routes
     * @param  callable(string): array{low: bool, fails: int}  $signals  per provider id
     * @return list<array<string, mixed>>
     */
    public function order(array $routes, string $profile, callable $signals): array
    {
        $desired = match ($profile) {
            TaskProfiler::COMPLEX => 3,
            TaskProfiler::CODING => 2,
            default => 1,
        };

        $scored = [];
        foreach ($routes as $index => $route) {
            $info = $this->catalog->info((string) $route['model']);
            $signal = $signals((string) $route['provider_id']);
            $score = 10 - abs($info['tier'] - $desired) * 3;
            // A stronger model is never worse than a weaker one for hard work.
            if ($info['tier'] > $desired && $desired >= 2) {
                $score += 2;
            }
            if ($info['coding'] && $profile !== TaskProfiler::SIMPLE) {
                $score += 2;
            }
            if ($signal['low']) {
                $score -= 8;
            }
            $score -= min(6, $signal['fails'] * 2);
            $scored[] = ['score' => $score, 'index' => $index, 'route' => $route];
        }

        usort($scored, static fn (array $a, array $b): int => [$b['score'], $a['index']] <=> [$a['score'], $b['index']]);

        return array_map(static fn (array $row): array => $row['route'], $scored);
    }
}
