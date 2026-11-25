<?php

declare(strict_types=1);

namespace App\Services\Mail;

use App\Models\User;
use App\Services\PlatformOwnerAccess;
use RuntimeException;

final class JmapOwnerPilot
{
    public function __construct(
        private readonly PlatformOwnerAccess $ownerAccess,
        private readonly JmapReadOnlyTransport $transport,
    ) {}

    /**
     * Internal source-only pilot. A future authenticated controller must also
     * require a recent password/passkey confirmation and never serialize config.
     *
     * @return list<array{id: string, name: string, parentId: ?string, role: ?string, sortOrder: int, totalEmails: int, unreadEmails: int}>
     */
    public function mailboxes(User $actor): array
    {
        $grant = $this->grant($actor);

        return $this->transport->mailboxes($grant['username'], $grant['token']);
    }

    /** @return array{ids: list<string>, position: int, total: int} */
    public function inboxPage(User $actor, int $position = 0): array
    {
        $grant = $this->grant($actor);

        return $this->transport->inboxPage($grant['username'], $grant['token'], $position);
    }

    /** @return array{username: string, token: string} */
    private function grant(User $actor): array
    {
        $ownerId = config('kmj-mail-engine.pilot_owner_id');
        if (config('kmj-mail-engine.pilot_enabled') !== true
            || ! is_int($ownerId) || $ownerId <= 0 || $actor->getKey() !== $ownerId) {
            throw new RuntimeException('KMJ mail pilot unavailable.');
        }

        // Re-read the current persisted authority. Do not trust a stale model.
        $current = User::query()->find($ownerId);
        if (! $current instanceof User || ! $this->ownerAccess->allows($current)) {
            throw new RuntimeException('KMJ mail pilot unavailable.');
        }

        $username = config('kmj-mail-engine.pilot_username');
        $token = config('kmj-mail-engine.pilot_access_token');
        if (! is_string($username) || strlen($username) > 254
            || preg_match('/\A[A-Za-z0-9][A-Za-z0-9._+-]{0,63}@kmjtechno\.com\z/D', $username) !== 1
            || ! is_string($token) || $token === '') {
            throw new RuntimeException('KMJ mail pilot unavailable.');
        }

        return ['username' => $username, 'token' => $token];
    }
}
