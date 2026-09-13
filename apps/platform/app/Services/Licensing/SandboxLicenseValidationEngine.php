<?php

namespace App\Services\Licensing;

use App\Models\LicenseRevocation;

final class SandboxLicenseValidationEngine
{
    public function __construct(
        private readonly LicenseValidator $phpValidator,
        private readonly RustSandboxLicenseVerifier $rustVerifier,
        private readonly string $mode = 'php',
    ) {}

    /**
     * @return array{valid: bool, reason: string|null, claims: array<string, mixed>|null}
     */
    public function validate(string $license): array
    {
        if (! in_array($this->mode, ['php', 'cross_check', 'rust'], true)) {
            return $this->invalid('validation_engine_unconfigured');
        }

        if ($this->mode === 'rust') {
            $rustResult = $this->rustVerifier->validate($license);

            if ($rustResult['valid'] === false) {
                return $rustResult;
            }

            $claims = $rustResult['claims'];

            if ($this->claimsComplete($claims) === false) {
                return $this->invalid('missing_claims');
            }

            $jti = $claims['jti'];

            if (LicenseRevocation::query()->where('jti', $jti)->exists()) {
                return $this->invalid('revoked', $claims);
            }

            return $rustResult;
        }

        $phpResult = $this->phpValidator->validate($license);

        if ($this->mode === 'php' || $phpResult['valid'] === false) {
            return $phpResult;
        }

        $rustResult = $this->rustVerifier->validate($license);

        if ($rustResult['valid'] === false || $this->claimsAgree($phpResult['claims'], $rustResult['claims']) === false) {
            return $this->invalid('verifier_disagreement');
        }

        return $phpResult;
    }

    /**
     * @param  array<string, mixed>|null  $claims
     */
    private function claimsComplete(?array $claims): bool
    {
        if ($claims === null || ($claims['environment'] ?? null) !== 'sandbox') {
            return false;
        }

        foreach (['jti', 'organization_id', 'product_id', 'entitlement_id'] as $claim) {
            if (! is_string($claims[$claim] ?? null) || $claims[$claim] === '') {
                return false;
            }
        }

        return is_int($claims['issued_at'] ?? null)
            && is_int($claims['expires_at'] ?? null);
    }

    /**
     * @param  array<string, mixed>|null  $phpClaims
     * @param  array<string, mixed>|null  $rustClaims
     */
    private function claimsAgree(?array $phpClaims, ?array $rustClaims): bool
    {
        if ($phpClaims === null || $rustClaims === null) {
            return false;
        }

        foreach (['environment', 'jti', 'organization_id', 'product_id', 'entitlement_id', 'issued_at', 'expires_at'] as $claim) {
            if (($phpClaims[$claim] ?? null) !== ($rustClaims[$claim] ?? null)) {
                return false;
            }
        }

        return true;
    }

    /**
     * @param  array<string, mixed>|null  $claims
     * @return array{valid: false, reason: string, claims: array<string, mixed>|null}
     */
    private function invalid(string $reason, ?array $claims = null): array
    {
        return [
            'valid' => false,
            'reason' => $reason,
            'claims' => $claims,
        ];
    }
}
