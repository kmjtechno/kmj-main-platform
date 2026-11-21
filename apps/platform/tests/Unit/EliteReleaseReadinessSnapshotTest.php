<?php

namespace Tests\Unit;

use App\Services\Operations\EliteReleaseReadinessSnapshot;
use Illuminate\Support\Facades\File;
use Tests\TestCase;

final class EliteReleaseReadinessSnapshotTest extends TestCase
{
    private string $receipt;

    protected function setUp(): void
    {
        parent::setUp();
        $this->receipt = storage_path('framework/testing/elite-release-readiness.json');
        File::ensureDirectoryExists(dirname($this->receipt), 0755);
        File::delete($this->receipt);
    }

    protected function tearDown(): void
    {
        if (is_link($this->receipt)) {
            unlink($this->receipt);
        } else {
            File::delete($this->receipt);
        }
        parent::tearDown();
    }

    /** @return array<string, mixed> */
    private function fixture(): array
    {
        $sha = str_repeat('a', 40);

        return [
            'schema' => 'kmj.elite.release-readiness.v1',
            'host' => 'KMJ-elite',
            'source' => 'fixed_root_preflight',
            'captured_at_unix' => time(),
            'decision' => 'READY_APPROVED_RELEASE',
            'current_release' => 'platform-'.str_repeat('b', 12),
            'approved_sha' => $sha,
            'expected_current_release' => 'platform-'.str_repeat('b', 12),
            'promoted_sha' => $sha,
            'candidate_sha' => $sha,
            'staging_origin_verified' => false,
            'scheduled_run_proven' => false,
            'independent_dr_verified' => false,
            'deploy_triggered' => false,
        ];
    }

    /** @param array<string, mixed> $data */
    private function write(array $data): void
    {
        File::put($this->receipt, json_encode($data, JSON_THROW_ON_ERROR));
        chmod($this->receipt, 0644);
    }

    /** @return array<string, mixed> */
    private function capture(): array
    {
        return (new EliteReleaseReadinessSnapshot($this->receipt, getmyuid()))->capture();
    }

    public function test_missing_fixed_root_receipt_is_never_ready(): void
    {
        $this->assertSame('unavailable', $this->capture()['status']);
    }

    public function test_exact_fresh_root_preflight_can_be_displayed_without_deploy_claim(): void
    {
        $this->write($this->fixture());
        $snapshot = $this->capture();

        $this->assertSame('preflight_ready_only', $snapshot['status']);
        $this->assertSame('READY_APPROVED_RELEASE', $snapshot['reason']);
        $this->assertFalse($snapshot['deploy_triggered']);
        $this->assertFalse($snapshot['staging_origin_verified']);
        $this->assertFalse($snapshot['independent_dr_verified']);
    }

    public function test_success_marker_with_contradictory_sha_or_predecessor_fails_closed(): void
    {
        foreach (['candidate_sha', 'promoted_sha'] as $key) {
            $value = $this->fixture();
            $value[$key] = str_repeat('c', 40);
            $this->write($value);
            $this->assertSame('unavailable', $this->capture()['status']);
        }

        $value = $this->fixture();
        $value['expected_current_release'] = 'platform-'.str_repeat('c', 12);
        $this->write($value);
        $this->assertSame('CONTRADICTORY_ROOT_RECEIPT', $this->capture()['reason']);
    }

    public function test_only_exact_live_identity_can_display_already_live(): void
    {
        $value = $this->fixture();
        $value['decision'] = 'ALREADY_LIVE';
        $value['current_release'] = 'platform-'.str_repeat('a', 12);
        $this->write($value);
        $this->assertSame('already_live_observed', $this->capture()['status']);
        $this->assertFalse($this->capture()['deploy_triggered']);

        $value['current_release'] = 'platform-'.str_repeat('b', 12);
        $this->write($value);
        $this->assertSame('unavailable', $this->capture()['status']);
    }

    public function test_stale_or_future_evidence_never_appears_ready(): void
    {
        foreach ([time() - 600, time() + 100] as $timestamp) {
            $value = $this->fixture();
            $value['captured_at_unix'] = $timestamp;
            $this->write($value);
            $this->assertSame('STALE_OR_FUTURE_RECEIPT', $this->capture()['reason']);
        }
    }

    public function test_untrusted_host_source_and_fake_execution_flags_fail_closed(): void
    {
        foreach ([
            ['host', 'google-vps1'],
            ['source', 'browser_generated'],
            ['deploy_triggered', true],
            ['independent_dr_verified', true],
            ['staging_origin_verified', true],
            ['scheduled_run_proven', true],
            ['decision', 'READY_WITHOUT_APPROVAL'],
        ] as [$key, $invalid]) {
            $value = $this->fixture();
            $value[$key] = $invalid;
            $this->write($value);
            $this->assertSame('unavailable', $this->capture()['status'], $key);
        }
    }

    public function test_world_writable_file_cannot_supply_authoritative_receipt(): void
    {
        $this->write($this->fixture());
        chmod($this->receipt, 0666);
        $this->assertSame('NO_TRUSTED_ROOT_RECEIPT', $this->capture()['reason']);
    }

    public function test_symlink_receipt_is_rejected_even_with_valid_json(): void
    {
        if (PHP_OS_FAMILY === 'Windows' || ! function_exists('symlink')) {
            $this->markTestSkipped('POSIX symlink defense.');
        }
        $value = $this->fixture();
        $target = $this->receipt.'.target';
        File::put($target, json_encode($value, JSON_THROW_ON_ERROR));
        try {
            if (! @symlink($target, $this->receipt)) {
                $this->markTestSkipped('Symlinks unavailable.');
            }
            $this->assertSame('NO_TRUSTED_ROOT_RECEIPT', $this->capture()['reason']);
        } finally {
            File::delete($target);
        }
    }
}
