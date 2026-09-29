<?php

namespace App\Console\Commands;

use App\Services\Events\OutboxBatchWorker;
use Illuminate\Console\Command;

final class ProcessOutboxCommand extends Command
{
    protected $signature = 'outbox:work {--limit=25} {--max-attempts=8} {--base-delay=15}';

    protected $description = 'Publish a bounded batch of due transactional outbox messages';

    public function handle(OutboxBatchWorker $worker): int
    {
        $result = $worker->run(
            (int) $this->option('limit'),
            (int) $this->option('max-attempts'),
            (int) $this->option('base-delay'),
        );

        $this->info(sprintf(
            'selected=%d published=%d failed=%d',
            $result['selected'],
            $result['published'],
            $result['failed'],
        ));

        return $result['failed'] > 0 ? self::FAILURE : self::SUCCESS;
    }
}
