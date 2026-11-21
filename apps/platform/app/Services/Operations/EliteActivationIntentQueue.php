<?php

namespace App\Services\Operations;

use App\Models\OperatorActionAudit;
use App\Models\User;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Str;
use InvalidArgumentException;
use RuntimeException;

/**
 * The owner's click creates an auditable, short-lived *intent*, never release
 * approval or permission for PHP to start a privileged service.
 */
final class EliteActivationIntentQueue
{
    public function __construct(
        private readonly EliteReleaseReadinessSnapshot $readiness,
    ) {}

    public function enqueue(
        User $user,
        string $approvedSha,
        string $expectedCurrentRelease,
        string $confirmation,
    ): void {
        if ($confirmation !== 'REQUEST_APPROVED_PRODUCTION_RELEASE') {
            throw new InvalidArgumentException('Explicit activation intent confirmation is required.');
        }

        $proof = $this->readiness->capture();
        self::assertEligible($proof, $approvedSha, $expectedCurrentRelease);

        $path = (string) config(
            'kmj.ops.activation_intent_path',
            storage_path('app/private/ops/production-activation-request.json'),
        );
        if ($path === '' || strlen($path) > 400 || is_link(dirname($path))) {
            throw new RuntimeException('Activation request inbox is not configured safely.');
        }

        File::ensureDirectoryExists(dirname($path), 0750, true);
        if (File::exists($path) || is_link($path)) {
            throw new RuntimeException('A production activation request is already pending.');
        }

        $id = (string) Str::uuid();
        $now = now()->timestamp;
        $payload = [
            'schema' => 'kmj.elite.production-activation-intent.v1',
            'intent_id' => $id,
            'actor_user_id' => (int) $user->getKey(),
            'action' => 'activate_existing_approved_release',
            'approved_sha' => $approvedSha,
            'expected_current_release' => $expectedCurrentRelease,
            'created_at_unix' => $now,
            'expires_at_unix' => $now + 90,
        ];

        // Audit before publishing so every executable request has a durable
        // owner event; failed publishes remain visible as failed attempts.
        $audit = OperatorActionAudit::query()->create([
            'actor_user_id' => $user->getKey(),
            'action' => 'release.activation_intent',
            'outcome' => 'queued_not_deployed',
            'metadata' => [
                'intent_id' => $id,
                'approved_sha' => $approvedSha,
                'expected_current_release' => $expectedCurrentRelease,
                'protected_preflight' => 'READY_APPROVED_RELEASE',
                'release_activated' => false,
            ],
        ]);

        $temporary = $path.'.'.Str::random(16).'.tmp';
        try {
            File::put(
                $temporary,
                json_encode($payload, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES),
                true,
            );
            chmod($temporary, 0640);
            // POSIX create-only hardlink: simultaneous owner double-click
            // cannot replace another pending request (nor a dangling symlink).
            if (! @link($temporary, $path)) {
                throw new RuntimeException('A production activation request is already pending or cannot be safely published.');
            }
        } catch (\Throwable $exception) {
            $audit->forceFill(['outcome' => 'blocked'])->save();
            throw $exception;
        } finally {
            File::delete($temporary);
        }
    }

    /** @param array<string, mixed> $proof */
    public static function assertEligible(
        array $proof,
        string $approvedSha,
        string $expectedCurrentRelease,
    ): void {
        if (preg_match('/\A[a-f0-9]{40}\z/D', $approvedSha) !== 1
            || preg_match('/\Aplatform-[a-f0-9]{12}\z/D', $expectedCurrentRelease) !== 1
            || $expectedCurrentRelease === 'platform-'.substr($approvedSha, 0, 12)
            || ($proof['status'] ?? null) !== 'preflight_ready_only'
            || ($proof['reason'] ?? null) !== 'READY_APPROVED_RELEASE'
            || ($proof['source'] ?? null) !== 'fixed_root_preflight'
            || ($proof['approved_sha'] ?? null) !== $approvedSha
            || ($proof['current_release'] ?? null) !== $expectedCurrentRelease
            || ($proof['expected_current_release'] ?? null) !== $expectedCurrentRelease
            || ($proof['promoted_sha'] ?? null) !== $approvedSha
            || ($proof['candidate_sha'] ?? null) !== $approvedSha
            || ($proof['deploy_triggered'] ?? null) !== false
            || ($proof['independent_dr_verified'] ?? null) !== false
        ) {
            throw new RuntimeException('A fresh independent exact-SHA owner preflight is required before activation intent.');
        }
    }
}
