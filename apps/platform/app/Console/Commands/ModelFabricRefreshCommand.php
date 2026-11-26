<?php

declare(strict_types=1);

namespace App\Console\Commands;

use App\Models\AiModelRequest;
use App\Models\AiProvider;
use App\Services\AiProviders\ModelFabricRuleApplier;
use App\Services\AiProviders\ProviderManager;
use Illuminate\Console\Command;
use Illuminate\Contracts\Encryption\DecryptException;

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
        $credentialFailures = 0;
        $applied = ['rules' => 0, 'approved' => 0];
        foreach (AiProvider::query()->where('enabled', true)->lazyById(100) as $provider) {
            try {
                $manager->test($provider);
            } catch (DecryptException) {
                // A damaged credential must not stop other providers from refreshing.
                // Never print the credential, exception text, or upstream body.
                $provider->health = 'auth_failed';
                $provider->health_checked_at = now();
                $provider->last_error_code = 'credential_decrypt_failed';
                $provider->models_cache = null;
                $provider->models_checked_at = null;
                $provider->rate_limit = ['status' => 'unknown'];
                $provider->save();
                $credentialFailures++;

                continue;
            }
            $checked++;
            if ($provider->health === 'ok') {
                $summary = $rules->apply($provider);
                $applied['rules'] += $summary['rules'];
                $applied['approved'] += $summary['approved'];
            }
        }
        $pruned = AiModelRequest::query()->where('created_at', '<', now()->subDays(90))->delete();

        $this->info("MODELFABRIC_REFRESH providers={$checked} rules={$applied['rules']} auto_approved={$applied['approved']} credential_failures={$credentialFailures} pruned={$pruned}");

        return self::SUCCESS;
    }
}
