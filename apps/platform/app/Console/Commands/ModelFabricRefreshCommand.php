<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Models\AiModelRequest;
use App\Models\AiProvider;
use App\Services\AiProviders\ModelFabricRuleApplier;
use App\Services\AiProviders\ProviderManager;
use Illuminate\Console\Command;

/**
 * Keeps model discovery fresh so routes do not silently go stale after 24 hours. It only calls the
 * read-only catalog endpoint (GET /models): no prompt is sent and nothing can be billed.
 */
final class ModelFabricRefreshCommand extends Command
{
    protected $signature = 'modelfabric:refresh';

    protected $description = 'Refresh provider model discovery (read-only) and prune old request metadata';

    public function handle(ProviderManager $manager, ModelFabricRuleApplier $rules): int
    {
        $checked = 0;
        foreach (AiProvider::query()->where('enabled', true)->get() as $provider) {
            $manager->test($provider);
            $checked++;
        }
        $applied = $rules->apply();
        $pruned = AiModelRequest::query()->where('created_at', '<', now()->subDays(90))->delete();

        $this->info("MODELFABRIC_REFRESH providers={$checked} rules={$applied['rules']} auto_approved={$applied['approved']} pruned={$pruned}");

        return self::SUCCESS;
    }
}
