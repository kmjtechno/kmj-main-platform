<?php

namespace App\Services\Operations;

use Throwable;

/**
 * Advisory owner view of a fixed root-published Elite preflight, never an
 * authorization to stage/activate or a substitute for Supervisor readback.
 */
final class EliteReleaseReadinessSnapshot
{
    public function __construct(
        private readonly ?string $testPath = null,
        private readonly int $trustedUid = 0,
    ) {}

    /** @return array<string, mixed> */
    public function capture(): array
    {
        $path = $this->testPath ?? (string) config(
            'kmj.ops.release_receipt_path',
            '/run/kmj-main-platform/release-readiness.json',
        );

        $bytes = $this->trustedRead($path);
        if ($bytes === null) {
            return $this->missing('NO_TRUSTED_ROOT_RECEIPT');
        }

        try {
            $data = json_decode($bytes, true, 16, JSON_THROW_ON_ERROR);
        } catch (Throwable) {
            return $this->missing('INVALID_ROOT_RECEIPT');
        }
        if (! is_array($data)
            || ($data['schema'] ?? null) !== 'kmj.elite.release-readiness.v1'
            || ($data['host'] ?? null) !== 'KMJ-elite'
            || ($data['source'] ?? null) !== 'fixed_root_preflight'
            || ($data['staging_origin_verified'] ?? null) !== false
            || ($data['scheduled_run_proven'] ?? null) !== false
            || ($data['independent_dr_verified'] ?? null) !== false
            || ($data['deploy_triggered'] ?? null) !== false
        ) {
            return $this->missing('INVALID_ROOT_RECEIPT');
        }

        $captured = $data['captured_at_unix'] ?? null;
        if (! is_int($captured) || $captured > time() + 5 || time() - $captured > 90) {
            return $this->missing('STALE_OR_FUTURE_RECEIPT');
        }

        $decision = $data['decision'] ?? null;
        if (! is_string($decision)
            || preg_match('/\A(?:READY_APPROVED_RELEASE|ALREADY_LIVE|BLOCKED_[A-Z0-9_]{1,80})\z/D', $decision) !== 1
        ) {
            return $this->missing('INVALID_ROOT_RECEIPT');
        }

        $approved = $this->sha($data['approved_sha'] ?? null);
        $current = $this->release($data['current_release'] ?? null);
        $expected = $this->release($data['expected_current_release'] ?? null);
        $promoted = $this->sha($data['promoted_sha'] ?? null);
        $candidate = $this->sha($data['candidate_sha'] ?? null);
        if ($decision === 'READY_APPROVED_RELEASE'
            && ($approved === null || $current === null || $expected !== $current
                || $promoted !== $approved || $candidate !== $approved)
        ) {
            return $this->missing('CONTRADICTORY_ROOT_RECEIPT');
        }

        if ($decision === 'ALREADY_LIVE'
            && ($approved === null || $current !== 'platform-'.substr($approved, 0, 12)
                || $promoted !== $approved || $candidate !== $approved)
        ) {
            return $this->missing('CONTRADICTORY_ROOT_RECEIPT');
        }

        return [
            'status' => match ($decision) {
                'READY_APPROVED_RELEASE' => 'preflight_ready_only',
                'ALREADY_LIVE' => 'already_live_observed',
                default => 'blocked',
            },
            'reason' => $decision,
            'captured_at_unix' => $captured,
            'current_release' => $current,
            'approved_sha' => $approved,
            'expected_current_release' => $expected,
            'promoted_sha' => $promoted,
            'candidate_sha' => $candidate,
            'staging_origin_verified' => false,
            'independent_dr_verified' => false,
            'deploy_triggered' => false,
            'source' => 'fixed_root_preflight',
        ];
    }

    /** @return array<string, mixed> */
    private function missing(string $reason): array
    {
        return [
            'status' => 'unavailable',
            'reason' => $reason,
            'captured_at_unix' => null,
            'current_release' => null,
            'approved_sha' => null,
            'expected_current_release' => null,
            'promoted_sha' => null,
            'candidate_sha' => null,
            'staging_origin_verified' => false,
            'independent_dr_verified' => false,
            'deploy_triggered' => false,
            'source' => 'unobserved',
        ];
    }

    private function sha(mixed $value): ?string
    {
        return is_string($value) && preg_match('/\A[0-9a-f]{40}\z/D', $value) === 1
            ? $value : null;
    }

    private function release(mixed $value): ?string
    {
        return is_string($value) && preg_match('/\Aplatform-[0-9a-f]{12}\z/D', $value) === 1
            ? $value : null;
    }

    private function trustedRead(string $path): ?string
    {
        if ($path === '' || strlen($path) > 400) {
            return null;
        }

        // The publisher uses a root-owned non-writable parent and a regular
        // root-owned single-link file. Never follow an attacker-owned symlink.
        $parent = @lstat(dirname($path));
        $before = @lstat($path);
        if (! is_array($parent) || ! is_array($before)
            || (($parent['mode'] & 0170000) !== 0040000)
            || (($before['mode'] & 0170000) !== 0100000)
            || $parent['uid'] !== $this->trustedUid
            || $before['uid'] !== $this->trustedUid
            || ($parent['mode'] & 0022) !== 0
            || ($before['mode'] & 0022) !== 0
            || $before['nlink'] !== 1
            || $before['size'] < 50 || $before['size'] > 4096
        ) {
            return null;
        }
        $stream = @fopen($path, 'rb');
        if ($stream === false) {
            return null;
        }
        try {
            $opened = fstat($stream);
            if (! is_array($opened) || $before['dev'] !== $opened['dev']
                || $before['ino'] !== $opened['ino']
                || $opened['size'] !== $before['size']
            ) {
                return null;
            }

            $contents = stream_get_contents($stream, 4097);

            return is_string($contents) && strlen($contents) === $before['size']
                ? $contents : null;
        } finally {
            fclose($stream);
        }
    }
}
