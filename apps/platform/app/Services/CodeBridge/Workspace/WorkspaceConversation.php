<?php

declare(strict_types=1);

namespace App\Services\CodeBridge\Workspace;

/** A conversation row the caller is already authorized to use (tenant, user and paired project). */
final readonly class WorkspaceConversation
{
    public function __construct(
        public string $id,
        public string $tenantId,
        public string $deviceId,
        public string $projectId,
        public int $userId,
        public string $title,
    ) {}
}
