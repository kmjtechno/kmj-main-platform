<?php

namespace App\Services\Operations;

use App\Models\OperatorActionAudit;
use App\Models\User;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Str;
use InvalidArgumentException;
use RuntimeException;

/**
 * The owner's click records a short-lived *intent* that the fixed root prepare broker may act on.
 * It is never a release approval, never an activation and never permission for PHP to run anything
 * privileged. The broker independently re-verifies the SHA is the current main head with every
 * exact-head check green and that the pinned owner helper is byte-identical before it runs.
 */
final class EliteReleasePrepareIntentQueue
{
    private const REPO_API = 'https://api.github.com/repos/kmjtechno/kmj-main-platform/commits/main';

    private const HEAD_CACHE_KEY = 'kmj-release-prepare:main-head:v1';

    private const STATES = [
        'preparing', 'prepare_failed', 'prepared_awaiting_activation',
        'migrating', 'migrate_failed', 'live_and_migrated',
    ];

    /**
     * Current GitHub main head as seen by the web app (display and click-time equality only).
     * Returns null when it cannot be verified; the root broker does its own check regardless.
     */
    public function mainHead(): ?string
    {
        $cached = Cache::get(self::HEAD_CACHE_KEY);
        if (is_string($cached) && preg_match('/\A[a-f0-9]{40}\z/D', $cached) === 1) {
            return $cached;
        }
        try {
            $response = Http::acceptJson()
                ->withHeaders(['X-GitHub-Api-Version' => '2022-11-28'])
                ->timeout(5)
                ->get(self::REPO_API);
        } catch (\Throwable) {
            return null;
        }
        $sha = $response->ok() ? $response->json('sha') : null;
        if (! is_string($sha) || preg_match('/\A[a-f0-9]{40}\z/D', $sha) !== 1) {
            return null;
        }
        Cache::put(self::HEAD_CACHE_KEY, $sha, now()->addSeconds(30));

        return $sha;
    }

    public function enqueue(
        User $user,
        string $approvedSha,
        string $confirmation,
        bool $backupRollbackAttested,
        bool $migrateAccepted,
    ): void {
        if ($confirmation !== 'REQUEST_RELEASE_PREPARE') {
            throw new InvalidArgumentException('Explicit release prepare confirmation is required.');
        }
        if ($backupRollbackAttested !== true || $migrateAccepted !== true) {
            throw new InvalidArgumentException('Both owner attestations are required.');
        }
        if (preg_match('/\A[a-f0-9]{40}\z/D', $approvedSha) !== 1) {
            throw new InvalidArgumentException('An exact 40-hex SHA is required.');
        }
        // Click-time equality: the SHA the owner saw must still be the verified main head.
        Cache::forget(self::HEAD_CACHE_KEY);
        if ($this->mainHead() !== $approvedSha) {
            throw new RuntimeException('The shown SHA is no longer the verified main head.');
        }

        $path = (string) config(
            'kmj.ops.prepare_intent_path',
            storage_path('app/private/ops/release-prepare-request.json'),
        );
        if ($path === '' || strlen($path) > 400 || is_link(dirname($path))) {
            throw new RuntimeException('Release prepare inbox is not configured safely.');
        }

        File::ensureDirectoryExists(dirname($path), 0750, true);
        if (File::exists($path) || is_link($path)) {
            throw new RuntimeException('A release prepare request is already pending.');
        }

        $id = (string) Str::uuid();
        $now = (int) now()->timestamp;
        $payload = [
            'schema' => 'kmj.elite.release-prepare-intent.v1',
            'intent_id' => $id,
            'actor_user_id' => (int) $user->getKey(),
            'action' => 'prepare_release_candidate',
            'approved_sha' => $approvedSha,
            'created_at_unix' => $now,
            'expires_at_unix' => $now + 90,
            'owner_backup_rollback_attested' => true,
            'migrate_after_activation_accepted' => true,
        ];

        $audit = OperatorActionAudit::query()->create([
            'actor_user_id' => $user->getKey(),
            'action' => 'release.prepare_intent',
            'outcome' => 'queued_not_prepared',
            'metadata' => [
                'intent_id' => $id,
                'approved_sha' => $approvedSha,
                'owner_backup_rollback_attested' => true,
                'migrate_after_activation_accepted' => true,
                'approval_written' => false,
                'release_activated' => false,
            ],
        ]);

        $temporary = $path.'.'.Str::random(16).'.tmp';
        try {
            File::put($temporary, json_encode($payload, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES), true);
            chmod($temporary, 0640);
            if (! @link($temporary, $path)) {
                throw new RuntimeException('A release prepare request is already pending or cannot be safely published.');
            }
        } catch (\Throwable $exception) {
            $audit->forceFill(['outcome' => 'blocked'])->save();
            throw $exception;
        } finally {
            File::delete($temporary);
        }
    }

    /**
     * Strictly validated broker status for display. A status is a report, never a release proof.
     *
     * @return array{state: string, approved_sha: string, detail: string, updated_at_unix: int}|null
     */
    public function status(): ?array
    {
        $path = (string) config(
            'kmj.ops.prepare_status_path',
            storage_path('app/private/ops/release-prepare-status.json'),
        );
        if ($path === '' || is_link($path) || ! is_file($path) || filesize($path) > 1024) {
            return null;
        }
        $decoded = json_decode((string) file_get_contents($path), true);
        $keys = is_array($decoded) ? array_keys($decoded) : [];
        sort($keys);
        if (! is_array($decoded)
            || $keys !== ['approved_sha', 'detail', 'schema', 'state', 'updated_at_unix']
            || ($decoded['schema'] ?? null) !== 'kmj.elite.release-prepare-status.v1'
            || ! in_array($decoded['state'], self::STATES, true)
            || ! is_string($decoded['approved_sha'])
            || preg_match('/\A[a-f0-9]{40}\z/D', $decoded['approved_sha']) !== 1
            || ! is_string($decoded['detail'])
            || strlen($decoded['detail']) > 120
            || ! is_int($decoded['updated_at_unix'])
        ) {
            return null;
        }

        return [
            'state' => $decoded['state'],
            'approved_sha' => $decoded['approved_sha'],
            'detail' => $decoded['detail'],
            'updated_at_unix' => $decoded['updated_at_unix'],
        ];
    }
}
