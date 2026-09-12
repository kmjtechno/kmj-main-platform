<?php

namespace App\Services\Operations;

use App\Models\OperatorActionAudit;
use App\Models\User;
use Illuminate\Support\Facades\Artisan;
use RuntimeException;
use Throwable;

final class OperatorActionRunner
{
    public function restartQueueWorkers(User $user): void
    {
        try {
            $exitCode = Artisan::call('queue:restart');

            if ($exitCode !== 0) {
                throw new RuntimeException('Queue restart command failed.');
            }

            $this->record($user, 'queue.restart', 'success', [
                'safe_action' => true,
                'exit_code' => $exitCode,
            ]);
        } catch (Throwable $exception) {
            $this->record($user, 'queue.restart', 'failed', [
                'safe_action' => true,
                'error_type' => $exception::class,
            ]);

            throw $exception;
        }
    }

    /** @param array<string, mixed> $metadata */
    private function record(User $user, string $action, string $outcome, array $metadata): void
    {
        OperatorActionAudit::query()->create([
            'actor_user_id' => $user->id,
            'action' => $action,
            'outcome' => $outcome,
            'metadata' => $metadata,
        ]);
    }
}
