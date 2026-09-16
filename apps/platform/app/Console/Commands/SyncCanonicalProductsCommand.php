<?php

namespace App\Console\Commands;

use App\Services\Commerce\CloudOSProductCatalog;
use Illuminate\Console\Command;

final class SyncCanonicalProductsCommand extends Command
{
    protected $signature = 'kmj:catalog:sync';

    protected $description = 'Synchronize canonical KMJ commercial products and entitlement policies';

    public function handle(CloudOSProductCatalog $cloudOS): int
    {
        $product = $cloudOS->sync();

        $this->info(sprintf(
            'Canonical product synced: %s (%s)',
            CloudOSProductCatalog::NAME,
            $product->getKey(),
        ));

        return self::SUCCESS;
    }
}
