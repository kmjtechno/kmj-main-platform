<?php

namespace App\Services\Licensing;

use DateTimeImmutable;

final class SandboxLicenseLifecycle
{
    public function __construct(
        private readonly SandboxLicenseIssuer $issuer,
        private readonly LicenseValidator $validator,
        private readonly LicenseRevoker $revoker,
    ) {}

    public function issue(
        int|string $organizationId,
        int|string $productId,
        int|string $entitlementId,
        DateTimeImmutable $expiresAt,
    ): string {
        return $this->issuer->issue($organizationId, $productId, $entitlementId, $expiresAt);
    }

    /**
     * @return array{valid: bool, reason: string|null, claims: array<string, mixed>|null}
     */
    public function validate(string $license): array
    {
        return $this->validator->validate($license);
    }

    public function revoke(string $jti, ?string $reason = null): void
    {
        $this->revoker->revoke($jti, $reason);
    }
}
