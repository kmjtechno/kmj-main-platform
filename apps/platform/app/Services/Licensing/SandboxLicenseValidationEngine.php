<?php

namespace App\Services\Licensing;

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
        if (! in_array($this->mode, ['php', 'cross_check'], true)) {
            return $this->invalid('validation_engine_unconfigured');
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
     * @return array{valid: false, reason: string, claims: null}
     */
    private function invalid(string $reason): array
    {
        return [
            'valid' => false,
            'reason' => $reason,
            'claims' => null,
        ];
    }
}
