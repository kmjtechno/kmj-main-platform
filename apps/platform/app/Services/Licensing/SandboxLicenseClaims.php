<?php

namespace App\Services\Licensing;

final readonly class SandboxLicenseClaims
{
    public function __construct(
        public string $jti,
        public string $organizationId,
        public string $productId,
        public string $entitlementId,
        public int $issuedAt,
        public int $expiresAt,
    ) {
    }
}
