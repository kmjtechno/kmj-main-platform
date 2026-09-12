<?php

namespace App\Services;

use App\Models\User;

final class PlatformOwnerAccess
{
    public function allows(User $user): bool
    {
        return (bool) $user->getAttribute('is_platform_owner')
            && $user->passkeys()->exists();
    }

    public function require(User $user): void
    {
        abort_unless($this->allows($user), 403);
    }
}
