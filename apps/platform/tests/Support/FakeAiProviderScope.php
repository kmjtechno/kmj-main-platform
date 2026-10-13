<?php

declare(strict_types=1);

namespace Tests\Support;

use App\Models\User;
use App\Services\AiProviders\ResolvesAiProviderScope;

final class FakeAiProviderScope implements ResolvesAiProviderScope
{
    /** @param array<int, array{organization_id: string, can_manage: bool}> $scopes */
    public function __construct(private readonly array $scopes) {}

    public function for(User $user): array
    {
        return $this->scopes[$user->id] ?? abort(404);
    }
}
