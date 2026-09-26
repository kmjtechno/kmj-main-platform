<?php

namespace App\Console\Commands;

use App\Services\Events\OutboxHealthSnapshot;
use Illuminate\Console\Command;

final class OutboxStatusCommand extends Command
{
    protected $signature = 'outbox:status {--max-attempts=8} {--json}';

    protected $description = 'Report transactional outbox pending, retry and exhausted-message health';

    public function handle(OutboxHealthSnapshot $snapshot): int
    {
        $state = $snapshot->capture((int) $this->option('max-attempts'));

        if ((bool) $this->option('json')) {
            $this->line((string) json_encode($state, JSON_UNESCAPED_SLASHES));

            return $state['exhausted'] > 0 ? self::FAILURE : self::SUCCESS;
        }

        $this->table(
            ['status', 'pending', 'due', 'retrying', 'exhausted', 'published'],
            [[
                $state['status'],
                $state['pending'],
                $state['due'],
                $state['retrying'],
                $state['exhausted'],
                $state['published'],
            ]],
        );

        if ($state['recent_exhausted'] !== []) {
            $this->newLine();
            $this->warn('Recent exhausted outbox messages:');
            $this->table(
                ['event', 'aggregate', 'attempts', 'last error'],
                array_map(
                    static fn (array $message): array => [
                        $message['event_type'],
                        $message['aggregate_type'].':'.$message['aggregate_id'],
                        $message['attempts'],
                        $message['last_error'] ?? '',
                    ],
                    $state['recent_exhausted'],
                ),
            );
        }

        return $state['exhausted'] > 0 ? self::FAILURE : self::SUCCESS;
    }
}
