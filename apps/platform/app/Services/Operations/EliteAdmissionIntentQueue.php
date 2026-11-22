<?php

namespace App\Services\Operations;

use App\Models\OperatorActionAudit;
use App\Models\User;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Str;
use InvalidArgumentException;
use RuntimeException;

/**
 * The owner's click records a short-lived *intent* that the fixed root admission
 * broker may act on. It is never release approval, never an admission file and
 * never permission for PHP to start a privileged service. The owner attests
 * here only that they personally completed authenticated QA on staging.
 */
final class EliteAdmissionIntentQueue
{
    public function __construct(
        private readonly EliteReleaseReadinessSnapshot $readiness,
    ) {}

    public function enqueue(
        User $user,
        string $approvedSha,
        string $expectedCurrentRelease,
        string $confirmation,
        bool $authenticatedQaAttested,
    ): void {
        if ($confirmation !== 'REQUEST_RELEASE_ADMISSION') {
            throw new InvalidArgumentException('Explicit admission intent confirmation is required.');
        }
        if ($authenticatedQaAttested !== true) {
            throw new InvalidArgumentException('The owner must attest that authenticated QA was completed.');
        }

        self::assertEligible($this->readiness->capture(), $approvedSha, $expectedCurrentRelease);

        $path = (string) config(
            'kmj.ops.admission_intent_path',
            storage_path('app/private/ops/release-admission-request.json'),
        );
        if ($path === '' || strlen($path) > 400 || is_link(dirname($path))) {
            throw new RuntimeException('Admission request inbox is not configured safely.');
        }

        File::ensureDirectoryExists(dirname($path), 0750, true);
        if (File::exists($path) || is_link($path)) {
            throw new RuntimeException('A release admission request is already pending.');
        }

        $id = (string) Str::uuid();
        $now = (int) now()->timestamp;
        $payload = [
            'schema' => 'kmj.elite.release-admission-intent.v1',
            'intent_id' => $id,
            'actor_user_id' => (int) $user->getKey(),
            'action' => 'write_release_admission',
            'approved_sha' => $approvedSha,
            'expected_current_release' => $expectedCurrentRelease,
            'created_at_unix' => $now,
            'expires_at_unix' => $now + 90,
            'owner_authenticated_qa_attested' => true,
        ];

        $audit = OperatorActionAudit::query()->create([
            'actor_user_id' => $user->getKey(),
            'action' => 'release.admission_intent',
            'outcome' => 'queued_not_admitted',
            'metadata' => [
                'intent_id' => $id,
                'approved_sha' => $approvedSha,
                'expected_current_release' => $expectedCurrentRelease,
                'owner_authenticated_qa_attested' => true,
                'admission_written' => false,
                'release_activated' => false,
            ],
        ]);

        $temporary = $path.'.'.Str::random(16).'.tmp';
        try {
            File::put($temporary, json_encode($payload, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES), true);
            chmod($temporary, 0640);
            if (! @link($temporary, $path)) {
                throw new RuntimeException('A release admission request is already pending or cannot be safely published.');
            }
        } catch (\Throwable $exception) {
            $audit->forceFill(['outcome' => 'blocked'])->save();
            throw $exception;
        } finally {
            File::delete($temporary);
        }
    }

    /**
     * Eligible only while the fixed root preflight has already matched the staged
     * candidate to the protected approval and is waiting on admission evidence.
     *
     * @param  array<string, mixed>  $proof
     */
    public static function assertEligible(
        array $proof,
        string $approvedSha,
        string $expectedCurrentRelease,
    ): void {
        if (preg_match('/\A[a-f0-9]{40}\z/D', $approvedSha) !== 1
            || preg_match('/\Aplatform-[a-f0-9]{12}\z/D', $expectedCurrentRelease) !== 1
            || $expectedCurrentRelease === 'platform-'.substr($approvedSha, 0, 12)
            || ($proof['status'] ?? null) !== 'blocked'
            || ($proof['reason'] ?? null) !== 'BLOCKED_ACCEPTANCE_SCHEMA'
            || ($proof['source'] ?? null) !== 'fixed_root_preflight'
            || ($proof['approved_sha'] ?? null) !== $approvedSha
            || ($proof['current_release'] ?? null) !== $expectedCurrentRelease
            || ($proof['expected_current_release'] ?? null) !== $expectedCurrentRelease
            || ($proof['deploy_triggered'] ?? null) !== false
        ) {
            throw new RuntimeException('A fresh exact-SHA preflight waiting only for admission evidence is required.');
        }
    }
}
