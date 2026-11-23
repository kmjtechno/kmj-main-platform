<?php

declare(strict_types=1);

namespace App\Services\Payments;

/**
 * Data returned by an external server-to-server LIVE payment verifier.
 * A signed webhook inbox row or browser callback is not this proof.
 */
final readonly class OmniDeskVerifiedLiveCapture
{
    public function __construct(
        public string $provider,
        public string $providerOrderId,
        public string $paymentReference,
        public string $environment,
        public string $currency,
        public int $amountMinor,
        public int $refundedMinor,
        public bool $captured,
    ) {}
}
