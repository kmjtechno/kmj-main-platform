<?php

namespace App\Console\Commands;

use App\Services\Commerce\KmjProductCatalog;
use Illuminate\Console\Command;

final class SyncCanonicalProductsCommand extends Command
{
    protected $signature = 'kmj:catalog:sync';

    protected $description = 'Synchronize canonical KMJ products and entitlement policy facts';

    public function handle(KmjProductCatalog $catalog): int
    {
        $products = $catalog->syncAll();

        foreach ($products as $slug => $product) {
            $this->info(sprintf(
                'Canonical product synced: %s (%s, %s)',
                $product->getAttribute('name'),
                $slug,
                $product->getKey(),
            ));
        }

        return self::SUCCESS;
    }
}
