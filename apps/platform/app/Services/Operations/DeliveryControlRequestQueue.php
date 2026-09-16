<?php

namespace App\Services\Operations;

use App\Models\OperatorActionAudit;
use App\Models\User;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Str;
use InvalidArgumentException;
use RuntimeException;

final class DeliveryControlRequestQueue
{
    private const ACTIONS = [
        'dispatch_worker',
        'requeue_safe_issue',
        'rerun_failed_ci',
    ];

    public function enqueue(
        User $user,
        string $action,
        ?int $issueNumber = null,
        ?int $runId = null,
    ): void {
        if (! in_array($action, self::ACTIONS, true)) {
            throw new InvalidArgumentException('Delivery control action is not allowlisted.');
        }

        $parameters = match ($action) {
            'dispatch_worker' => [],
            'requeue_safe_issue' => ['issue_number' => $this->positive($issueNumber)],
            'rerun_failed_ci' => ['run_id' => $this->positive($runId)],
        };

        $path = (string) config('kmj.ops.control_request_path');
        if ($path === '') {
            throw new RuntimeException('Delivery control request path is not configured.');
        }

        File::ensureDirectoryExists(dirname($path), 0750, true);
        if (File::exists($path)) {
            throw new RuntimeException('A delivery control request is already pending.');
        }

        $payload = [
            'version' => 1,
            'request_id' => (string) Str::uuid(),
            'requested_at' => now()->toIso8601String(),
            'actor_user_id' => $user->getKey(),
            'action' => $action,
            'parameters' => $parameters,
        ];

        $temporary = $path.'.'.Str::random(12).'.tmp';
        try {
            File::put($temporary, json_encode($payload, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES), true);
            chmod($temporary, 0640);
            if (! @rename($temporary, $path)) {
                throw new RuntimeException('Delivery control request could not be published atomically.');
            }
        } finally {
            File::delete($temporary);
        }

        OperatorActionAudit::query()->create([
            'actor_user_id' => $user->getKey(),
            'action' => 'delivery.'.$action,
            'outcome' => 'queued',
            'metadata' => [
                'safe_action' => true,
                'request_id' => $payload['request_id'],
                'parameters' => $parameters,
            ],
        ]);
    }

    private function positive(?int $value): int
    {
        if ($value === null || $value < 1) {
            throw new InvalidArgumentException('Delivery control identifier must be positive.');
        }

        return $value;
    }
}
