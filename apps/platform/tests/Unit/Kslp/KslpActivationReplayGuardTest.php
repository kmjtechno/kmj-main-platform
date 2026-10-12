<?php

declare(strict_types=1);

namespace Tests\Unit\Kslp;

use App\Services\Licensing\Kslp\KslpActivationReplayGuard;
use PHPUnit\Framework\TestCase;

final class KslpActivationReplayGuardTest extends TestCase
{
    /** @return array<string, mixed> */
    private function activation(): array
    {
        return [
            'license_id' => 'license-1',
            'server_identity' => 'ed25519:device-key-1',
            'machine_identity_hash' => str_repeat('a', 64),
            'deactivated_at' => null,
        ];
    }

    public function test_identical_license_device_and_machine_retry_is_allowed(): void
    {
        KslpActivationReplayGuard::requireMatch(
            $this->activation(), 'license-1', 'ed25519:device-key-1', str_repeat('a', 64),
        );
        self::assertTrue(true);
    }

    public function test_foreign_customer_cannot_replay_idempotency_record(): void
    {
        $this->expectExceptionMessage('KSLP_ACTIVATION_CONFLICT');
        KslpActivationReplayGuard::requireMatch(
            $this->activation(), 'license-2', 'ed25519:device-key-1', str_repeat('a', 64),
        );
    }

    public function test_different_device_key_is_rejected(): void
    {
        $this->expectExceptionMessage('KSLP_ACTIVATION_CONFLICT');
        KslpActivationReplayGuard::requireMatch(
            $this->activation(), 'license-1', 'ed25519:device-key-2', str_repeat('a', 64),
        );
    }

    public function test_different_hardware_fingerprint_is_rejected(): void
    {
        $this->expectExceptionMessage('KSLP_ACTIVATION_CONFLICT');
        KslpActivationReplayGuard::requireMatch(
            $this->activation(), 'license-1', 'ed25519:device-key-1', str_repeat('b', 64),
        );
    }

    public function test_deactivated_activation_is_rejected(): void
    {
        $this->expectExceptionMessage('KSLP_ACTIVATION_CONFLICT');
        KslpActivationReplayGuard::requireMatch(
            array_replace($this->activation(), ['deactivated_at' => '2026-10-12 10:00:00']),
            'license-1', 'ed25519:device-key-1', str_repeat('a', 64),
        );
    }

    public function test_missing_machine_hash_is_rejected(): void
    {
        $this->expectExceptionMessage('KSLP_ACTIVATION_CONFLICT');
        KslpActivationReplayGuard::requireMatch(
            array_replace($this->activation(), ['machine_identity_hash' => null]),
            'license-1', 'ed25519:device-key-1', str_repeat('a', 64),
        );
    }

    public function test_blank_requested_license_is_rejected(): void
    {
        $this->expectExceptionMessage('KSLP_ACTIVATION_CONFLICT');
        KslpActivationReplayGuard::requireMatch(
            $this->activation(), '', 'ed25519:device-key-1', str_repeat('a', 64),
        );
    }
}
