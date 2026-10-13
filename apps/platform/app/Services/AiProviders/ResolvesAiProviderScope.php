<?php

declare(strict_types=1);

namespace App\Services\AiProviders;

use App\Models\User;

interface ResolvesAiProviderScope
{
    /**
     * The one organization this user may see providers for (404 when none) and
     * whether they may change them.
     *
     * @return array{organization_id: string, can_manage: bool}
     */
    public function for(User $user): array;
}
