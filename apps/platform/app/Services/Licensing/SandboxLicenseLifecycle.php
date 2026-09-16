<?php

namespace App\Services\Licensing;

use DateTimeImmutable;

final class SandboxLicenseLifecycle
{
    public function __construct(
        private readonly SandboxLicenseIssuer $issuer,
        private readonly SandboxLicenseValidationEngine $validator,
        private readonly LicenseRevoker $revoker,
        private readonly SandboxProductAuthorityValidator $productAuthority,
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
        $result = $this->validator->validate($license);

        if ($result['valid'] === false || ! is_array($result['claims'])) {
            return $result;
        }

        $failureReason = $this->productAuthority->failureReason($result['claims']);

        if ($failureReason !== null) {
            return [
                'valid' => false,
                'reason' => $failureReason,
                'claims' => $result['claims'],
            ];
        }

        return $result;
    }

    public function revoke(string $jti, ?string $reason = null): void
    {
        $this->revoker->revoke($jti, $reason);
    }
}
